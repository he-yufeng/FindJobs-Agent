from job_matcher import JobMatcher


def test_parse_job_skills_accepts_pipeline_formats():
    matcher = JobMatcher()

    parsed = matcher.parse_job_skills(
        "Python , 5 , AI | Machine Learning %> 4 , AI | SQL: 3 | python, 2, AI"
    )

    assert parsed == [("Python", 5), ("Machine Learning", 4), ("SQL", 3)]


def test_match_jobs_is_case_insensitive_and_keeps_sorting():
    matcher = JobMatcher()
    resume_skills = [
        {"skill_name": "python", "score": 5},
        {"skill_name": "machine learning", "score": 4},
    ]
    jobs = [
        {"id": "low", "skill_tags_raw": "SQL , 4 , AI", "required_skills": []},
        {
            "id": "high",
            "skill_tags_raw": "Python , 5 , AI | Machine Learning , 4 , AI",
            "required_skills": [],
        },
    ]

    matches = matcher.match_jobs(resume_skills, jobs)

    assert matches[0]["job_id"] == "high"
    assert matches[0]["matched_skills"] == ["Python", "Machine Learning"]
    assert matches[0]["match_score"] > matches[1]["match_score"]


def test_match_jobs_falls_back_to_required_skills():
    matcher = JobMatcher()
    matches = matcher.match_jobs(
        [{"skill_name": "React", "score": 4}],
        [{"id": "frontend", "skill_tags_raw": "", "required_skills": ["React"]}],
    )

    assert matches[0]["matched_skills"] == ["React"]


def test_match_jobs_reports_missing_skills_gap():
    matcher = JobMatcher()
    resume_skills = [{"skill_name": "Python", "score": 5}]
    jobs = [
        {
            "id": "backend",
            "skill_tags_raw": "Python , 5 , AI | Kubernetes , 4 , AI | Go , 3 , AI",
            "required_skills": [],
        }
    ]

    matches = matcher.match_jobs(resume_skills, jobs)

    assert matches[0]["matched_skills"] == ["Python"]
    # the job wants Kubernetes and Go, which the resume lacks -> surfaced as a gap
    assert matches[0]["missing_skills"] == ["Kubernetes", "Go"]
