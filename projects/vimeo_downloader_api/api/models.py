from django.db import models
from django.contrib.auth.models import User
import uuid

class VimeoVideo(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='vimeo_videos')
    original_url = models.URLField(max_length=500)
    video_id = models.CharField(max_length=100, blank=True)
    
    # Playlist/master data
    playlist_json = models.JSONField(null=True, blank=True)
    master_json = models.JSONField(null=True, blank=True)
    base_url = models.CharField(max_length=500, blank=True)
    
    # Video metadata
    title = models.CharField(max_length=255, blank=True)
    thumbnail_url = models.URLField(max_length=500, blank=True)
    duration = models.IntegerField(default=0)  # in seconds
    available_resolutions = models.JSONField(default=list)
    
    # Status tracking
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('ready', 'Ready'),
        ('error', 'Error'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']

class VideoDownload(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    video = models.ForeignKey(VimeoVideo, on_delete=models.CASCADE, related_name='downloads')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Download settings
    resolution = models.CharField(max_length=20)  # e.g., '1080p', '720p'
    include_audio = models.BooleanField(default=True)
    
    # Status tracking
    STATUS_CHOICES = [
        ('queued', 'Queued'),
        ('downloading', 'Downloading'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('error', 'Error'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='queued')
    
    # Progress tracking
    progress = models.FloatField(default=0.0)  # 0.0 to 1.0
    downloaded_chunks = models.IntegerField(default=0)
    total_chunks = models.IntegerField(default=0)
    
    # File info
    file_size = models.BigIntegerField(default=0)  # in bytes
    estimated_duration = models.IntegerField(default=0)  # in seconds
    
    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']