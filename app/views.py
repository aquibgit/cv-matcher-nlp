from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import JobRequirement
from .utils import score_cv_for_requirement, extract_text_from_uploaded_file



def requirements_list(request):
    """List all job requirements."""
    requirements = JobRequirement.objects.all().order_by("-created_at")
    return render(request, "requirements_list.html", {
        "requirements": requirements,
    })


def add_requirement(request):
    """Add a new job requirement (JD)."""
    if request.method == "POST":
        title = request.POST.get("title")
        location = request.POST.get("location")
        experience = request.POST.get("experience")
        skills = request.POST.get("skills")
        job_description = request.POST.get("job_description")

        if not title or not job_description:
            messages.error(request, "Title and Job Description are required.")
            return render(request, "add_requirement.html", {
                "title": title,
                "location": location,
                "experience": experience,
                "skills": skills,
                "job_description": job_description,
            })

        JobRequirement.objects.create(
            title=title,
            location=location or "",
            experience=experience or "",
            skills=skills or "",
            job_description=job_description,
        )

        messages.success(request, "Job requirement added successfully.")
        return redirect("requirements_list")

    return render(request, "add_requirement.html")


def upload_cv_view(request):
    requirements = JobRequirement.objects.all().order_by("-created_at")
    result = None
    cv_text = ""
    selected_requirement_id = ""

    if request.method == "POST":
        selected_requirement_id = request.POST.get("requirement_id", "")
        cv_text = request.POST.get("cv_text", "").strip()
        cv_file = request.FILES.get("cv_file")

        if not selected_requirement_id:
            messages.error(request, "Please select a job requirement.")
        else:
            requirement = get_object_or_404(JobRequirement, id=selected_requirement_id)

            # If text is empty but file uploaded → parse file using utils.py
            if not cv_text and cv_file:
                cv_text = extract_text_from_uploaded_file(cv_file)

            if not cv_text:
                messages.error(request, "Please upload a CV file or paste CV text.")
            else:
                result = score_cv_for_requirement(cv_text, requirement)

    return render(request, "upload_cv.html", {
        "requirements": requirements,
        "selected_requirement_id": selected_requirement_id,
        "cv_text": cv_text,
        "result": result,
    })

def requirement_detail(request, pk):
    requirement = get_object_or_404(JobRequirement, pk=pk)
    return render(request, "requirement_detail.html", {
        "requirement": requirement
    })




