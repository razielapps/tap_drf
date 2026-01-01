import os
import json
import base64
import requests
import asyncio
import tempfile
from urllib.parse import urlparse, urljoin
from django.utils import timezone
from django.http import StreamingHttpResponse, JsonResponse
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
from concurrent.futures import ThreadPoolExecutor
import aiohttp
from asgiref.sync import sync_to_async, async_to_sync

from .models import VimeoVideo, VideoDownload
from .serializers import (
    VimeoVideoSerializer,
    VideoDownloadSerializer,
    CreateVideoRequestSerializer,
    CreateDownloadRequestSerializer,
)


class HealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "ok"})


class SubmitVideoUrlView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Submit a Vimeo video URL for processing
        POST /api/submit-url/
        """
        serializer = CreateVideoRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        url = serializer.validated_data["url"]

        # Check if already exists
        existing = VimeoVideo.objects.filter(
            user=request.user, original_url=url
        ).first()

        if existing:
            return Response(
                {
                    "message": "Video already processed",
                    "video": VimeoVideoSerializer(existing).data,
                }
            )

        # Create video record
        video = VimeoVideo.objects.create(
            user=request.user, original_url=url, status="pending"
        )

        # Start background processing
        self.process_vimeo_url_background(video.id)

        return Response(
            {"message": "Video submitted for processing", "video_id": str(video.id)},
            status=status.HTTP_202_ACCEPTED,
        )

    def process_vimeo_url_background(self, video_id):
        """
        Background task to process Vimeo URL
        """
        import threading

        thread = threading.Thread(target=self.process_vimeo_url_task, args=(video_id,))
        thread.daemon = True
        thread.start()

    def process_vimeo_url_task(self, video_id):
        """
        Process Vimeo URL to extract playlist/master.json
        """
        try:
            video = VimeoVideo.objects.get(id=video_id)
            video.status = "processing"
            video.save()

            url = video.original_url

            # Extract video ID and basic info
            parsed = urlparse(url)
            video_id_str = (
                parsed.path.split("/")[-2] if "video" in parsed.path else None
            )

            # Convert to playlist/master.json if needed
            if "playlist.json" not in url and "master.json" not in url:
                # This would need actual Vimeo API logic to get the actual streaming URLs
                # For now, we'll assume the provided URL is the final one
                pass

            # Fetch playlist/master.json
            response = requests.get(url)
            if response.status_code != 200:
                raise Exception(f"Failed to fetch playlist: {response.status_code}")

            data = response.json()
            video.playlist_json = data

            # Extract base URL
            if "base_url" in data:
                video.base_url = data["base_url"]
            else:
                # Extract base URL from the original URL
                if "/playlist/" in url:
                    base_url = url[: url.rfind("/playlist/") + 1]
                else:
                    base_url = (
                        url[: url.rfind("/", 0, -26) + 1] if url.count("/") > 5 else url
                    )
                video.base_url = base_url

            # Extract video metadata
            video.title = f"Vimeo Video {video_id_str or 'Unknown'}"

            # Extract available resolutions
            resolutions = []
            if "video" in data:
                for v in data["video"]:
                    if "height" in v:
                        resolutions.append(f"{v['height']}p")
                    elif "width" in v:
                        resolutions.append(f"{v['width']}p")

            video.available_resolutions = resolutions

            # Extract duration (from segments)
            if "video" in data and len(data["video"]) > 0:
                if "duration" in data["video"][0]:
                    video.duration = int(data["video"][0]["duration"])
                elif "segments" in data["video"][0]:
                    total_duration = sum(
                        seg.get("duration", 0) for seg in data["video"][0]["segments"]
                    )
                    video.duration = int(total_duration)

            # Extract thumbnail (simplified)
            video.thumbnail_url = (
                f"https://vimeo.com/{video_id_str}" if video_id_str else ""
            )

            video.status = "ready"
            video.processed_at = timezone.now()
            video.save()

            return True

        except Exception as e:
            video = VimeoVideo.objects.get(id=video_id)
            video.status = "error"
            video.save()
            print(f"Error processing video: {e}")
            return False


class GetVideoInfoView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, video_id):
        """
        Get video information including available resolutions
        GET /api/video-info/{video_id}/
        """
        try:
            video = VimeoVideo.objects.get(id=video_id, user=request.user)
        except VimeoVideo.DoesNotExist:
            return Response(
                {"error": "Video not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if video.status != "ready":
            return Response(
                {"status": video.status, "message": "Video is still processing"},
                status=status.HTTP_202_ACCEPTED,
            )

        serializer = VimeoVideoSerializer(video)
        return Response(serializer.data)


class StartDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Start downloading a video with specific resolution
        POST /api/start-download/
        """
        serializer = CreateDownloadRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        video_id = serializer.validated_data["video_id"]
        resolution = serializer.validated_data["resolution"]

        try:
            video = VimeoVideo.objects.get(id=video_id, user=request.user)
        except VimeoVideo.DoesNotExist:
            return Response(
                {"error": "Video not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if video.status != "ready":
            return Response(
                {"error": "Video not ready for download"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate resolution
        if resolution not in video.available_resolutions:
            return Response(
                {"error": f"Resolution {resolution} not available"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create download record
        download = VideoDownload.objects.create(
            video=video, user=request.user, resolution=resolution
        )

        # Calculate estimated download info
        self.calculate_download_info(download)

        # Start download in background
        self.start_video_download_background(download.id)

        return Response(
            {"message": "Download started", "download_id": str(download.id)},
            status=status.HTTP_202_ACCEPTED,
        )

    def calculate_download_info(self, download):
        """
        Calculate download information (size, duration, chunks)
        """
        video = download.video
        playlist = video.playlist_json

        # Find the selected resolution
        selected_res = int(download.resolution.replace("p", ""))

        video_data = None
        for v in playlist.get("video", []):
            if v.get("height") == selected_res:
                video_data = v
                break

        if not video_data:
            download.status = "error"
            download.save()
            return

        # Calculate total chunks
        total_chunks = len(video_data.get("segments", []))
        download.total_chunks = total_chunks

        # Estimate file size from segments
        total_size = 0
        if "segments" in video_data:
            for segment in video_data["segments"]:
                if "size" in segment:
                    total_size += segment["size"]
                elif "length" in segment:
                    total_size += segment["length"]

        # If no size in segments, estimate from bitrate
        if total_size == 0 and "bitrate" in video_data:
            bitrate = video_data["bitrate"]  # bits per second
            total_size = (bitrate * video.duration) / 8  # Convert to bytes

        download.file_size = total_size

        # Calculate estimated download time (assuming 5 Mbps download speed)
        estimated_time = total_size / (5 * 125000)  # 5 Mbps in bytes per second
        download.estimated_duration = int(estimated_time)

        download.save()

    def start_video_download_background(self, download_id):
        """
        Start background download task
        """
        import threading

        thread = threading.Thread(target=self.download_video_task, args=(download_id,))
        thread.daemon = True
        thread.start()

    def download_video_task(self, download_id):
        """
        Download video chunks task
        """
        try:
            download = VideoDownload.objects.get(id=download_id)
            download.status = "downloading"
            download.started_at = timezone.now()
            download.save()

            # This is where you would implement the actual chunk downloading
            # For now, we'll just simulate completion
            import time

            for i in range(download.total_chunks):
                time.sleep(0.5)  # Simulate download time
                download.downloaded_chunks = i + 1
                download.progress = (i + 1) / download.total_chunks
                download.save()

            download.status = "completed"
            download.completed_at = timezone.now()
            download.save()

        except Exception as e:
            download = VideoDownload.objects.get(id=download_id)
            download.status = "error"
            download.save()
            print(f"Error downloading video: {e}")


class StreamChunkView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, download_id):
        """
        Stream a specific chunk of the video
        GET /api/stream-chunk/{download_id}/?chunk=0&type=video
        """
        try:
            download = VideoDownload.objects.get(id=download_id, user=request.user)
        except VideoDownload.DoesNotExist:
            return Response(
                {"error": "Download not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if download.status not in ["downloading", "processing"]:
            return Response(
                {"error": "Download not in progress"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        chunk_number = request.GET.get("chunk", "0")
        chunk_type = request.GET.get("type", "video")  # 'video' or 'audio'

        try:
            chunk_number = int(chunk_number)
        except ValueError:
            return Response(
                {"error": "Invalid chunk number"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Get chunk data
        chunk_data = self.get_chunk_data(download, chunk_number, chunk_type)

        if chunk_data is None:
            return Response(
                {"error": "Chunk not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Stream the chunk
        response = StreamingHttpResponse(
            chunk_data,
            content_type="video/mp4" if chunk_type == "video" else "audio/mp4",
            status=200,
        )
        response["Content-Disposition"] = (
            f'attachment; filename="chunk_{chunk_number}.mp4"'
        )
        response["X-Chunk-Number"] = str(chunk_number)
        response["X-Total-Chunks"] = str(download.total_chunks)

        # Update progress
        download.downloaded_chunks = chunk_number + 1
        download.progress = download.downloaded_chunks / download.total_chunks
        download.save()

        return response

    def get_chunk_data(self, download, chunk_number, chunk_type):
        """
        Fetch chunk data from Vimeo
        """
        video = download.video
        playlist = video.playlist_json

        if chunk_type == "video":
            # Find video data for selected resolution
            selected_res = int(download.resolution.replace("p", ""))
            video_data = None
            for v in playlist.get("video", []):
                if v.get("height") == selected_res:
                    video_data = v
                    break

            if not video_data:
                return None

            segments = video_data.get("segments", [])
            if chunk_number >= len(segments):
                return None

            segment = segments[chunk_number]
            segment_url = urljoin(
                video.base_url + video_data.get("base_url", ""), segment["url"]
            )

        else:  # audio
            # Get best audio quality
            if not playlist.get("audio"):
                return None

            audio_data = max(
                playlist.get("audio", []), key=lambda x: x.get("bitrate", 0)
            )
            segments = audio_data.get("segments", [])

            if chunk_number >= len(segments):
                return None

            segment = segments[chunk_number]
            segment_url = urljoin(
                video.base_url + audio_data.get("base_url", ""), segment["url"]
            )

        # Download chunk
        try:
            response = requests.get(segment_url, stream=True, timeout=30)
            if response.status_code == 200:
                # Return generator for streaming
                def generate():
                    for chunk in response.iter_content(chunk_size=8192):
                        yield chunk

                return generate()
        except Exception as e:
            print(f"Error downloading chunk: {e}")

        return None


class DownloadProgressView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, download_id):
        """
        Get download progress
        GET /api/download-progress/{download_id}/
        """
        try:
            download = VideoDownload.objects.get(id=download_id, user=request.user)
        except VideoDownload.DoesNotExist:
            return Response(
                {"error": "Download not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = VideoDownloadSerializer(download)
        return Response(serializer.data)


class MergeVideoAudioView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, download_id):
        """
        Merge video and audio after download completion
        POST /api/merge-video-audio/{download_id}/
        """
        try:
            download = VideoDownload.objects.get(id=download_id, user=request.user)
        except VideoDownload.DoesNotExist:
            return Response(
                {"error": "Download not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if download.status != "completed":
            return Response(
                {"error": "Download not completed"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Update status to processing
        download.status = "processing"
        download.save()

        # Start merging process in background
        self.merge_video_audio_background(download_id)

        return Response(
            {"message": "Video and audio merging started"},
            status=status.HTTP_202_ACCEPTED,
        )

    def merge_video_audio_background(self, download_id):
        """
        Start background task to merge video and audio
        """
        import threading

        thread = threading.Thread(
            target=self.merge_video_audio_task, args=(download_id,)
        )
        thread.daemon = True
        thread.start()

    def merge_video_audio_task(self, download_id):
        """
        Task to merge video and audio using moviepy
        """
        try:
            download = VideoDownload.objects.get(id=download_id)

            # Create temporary directory
            import tempfile

            temp_dir = tempfile.mkdtemp()

            # Download video and audio files
            video_path = os.path.join(temp_dir, "video.mp4")
            audio_path = os.path.join(temp_dir, "audio.mp4")
            output_path = os.path.join(temp_dir, "output.mp4")

            # Download all video chunks
            self.download_all_chunks(download, "video", video_path)

            # Download all audio chunks
            self.download_all_chunks(download, "audio", audio_path)

            # Merge using moviepy
            from moviepy.editor import VideoFileClip, AudioFileClip

            video_clip = VideoFileClip(video_path)
            audio_clip = AudioFileClip(audio_path)
            video_clip_with_audio = video_clip.set_audio(audio_clip)

            # Write merged video
            video_clip_with_audio.write_videofile(
                output_path, codec="libx264", audio_codec="aac"
            )

            # Clean up temp files
            os.remove(video_path)
            os.remove(audio_path)

            # Update download status
            download.status = "completed"
            download.save()

            # Return the merged file path (in production, you'd upload this to storage)
            print(f"Merged video saved to: {output_path}")

        except Exception as e:
            download = VideoDownload.objects.get(id=download_id)
            download.status = "error"
            download.save()
            print(f"Error merging video and audio: {e}")

    def download_all_chunks(self, download, chunk_type, output_path):
        """
        Download all chunks of a specific type
        """
        video = download.video
        playlist = video.playlist_json

        if chunk_type == "video":
            selected_res = int(download.resolution.replace("p", ""))
            media_data = None
            for v in playlist.get("video", []):
                if v.get("height") == selected_res:
                    media_data = v
                    break
        else:
            media_data = max(
                playlist.get("audio", []), key=lambda x: x.get("bitrate", 0)
            )

        if not media_data:
            raise Exception(f"No {chunk_type} data found")

        # Download init segment
        init_segment = base64.b64decode(media_data["init_segment"])

        with open(output_path, "wb") as file:
            file.write(init_segment)

            # Download all segments
            for segment in media_data.get("segments", []):
                segment_url = urljoin(
                    video.base_url + media_data.get("base_url", ""), segment["url"]
                )
                response = requests.get(segment_url, stream=True)
                if response.status_code == 200:
                    for chunk in response.iter_content(chunk_size=8192):
                        file.write(chunk)


class UserVideosView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Get all videos for the current user
        GET /api/user-videos/
        """
        videos = VimeoVideo.objects.filter(user=request.user)
        serializer = VimeoVideoSerializer(videos, many=True)
        return Response(serializer.data)


class UserDownloadsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Get all downloads for the current user
        GET /api/user-downloads/
        """
        downloads = VideoDownload.objects.filter(user=request.user)
        serializer = VideoDownloadSerializer(downloads, many=True)
        return Response(serializer.data)
