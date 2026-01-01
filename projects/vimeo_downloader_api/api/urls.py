from django.urls import path
from .views import (
    HealthView,
    SubmitVideoUrlView,
    GetVideoInfoView,
    StartDownloadView,
    StreamChunkView,
    DownloadProgressView,
    MergeVideoAudioView,
    UserVideosView,
    UserDownloadsView
)

urlpatterns = [
    # Health check
    path('api/health/', HealthView.as_view(), name='health'),
    
    # Video submission and info
    path('api/submit-url/', SubmitVideoUrlView.as_view(), name='submit-url'),
    path('api/video-info/<uuid:video_id>/', GetVideoInfoView.as_view(), name='video-info'),
    path('api/user-videos/', UserVideosView.as_view(), name='user-videos'),
    
    # Download management
    path('api/start-download/', StartDownloadView.as_view(), name='start-download'),
    path('api/stream-chunk/<uuid:download_id>/', StreamChunkView.as_view(), name='stream-chunk'),
    path('api/download-progress/<uuid:download_id>/', DownloadProgressView.as_view(), name='download-progress'),
    path('api/merge-video-audio/<uuid:download_id>/', MergeVideoAudioView.as_view(), name='merge-video-audio'),
    path('api/user-downloads/', UserDownloadsView.as_view(), name='user-downloads'),
]