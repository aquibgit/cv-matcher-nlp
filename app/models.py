# jobs/models.py
from django.db import models


class JobRequirement(models.Model):
    title = models.CharField(max_length=200)
    location = models.CharField(max_length=200, blank=True)
    experience = models.CharField(max_length=100, blank=True)  # e.g. "0–2 years"
    skills = models.TextField(blank=True)  # e.g. "Python, Django, REST"
    job_description = models.TextField()   # full JD used for CV matching
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

