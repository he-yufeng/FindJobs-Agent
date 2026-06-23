from job_matcher import JobMatcher


def test_parse_job_skills_accepts_pipeline_formats():
    matcher = JobMatcher()

    parsed = matcher.parse_job_skills(
        "Python , 5 , AI | Machine Learning %> 4 , AI | SQL: 3 | python, 2, AI"
    )

    assert parsed == [("Python", 5), ("Machine Learning", 4), ("SQL", 3)]


def test_parse_job_skills_keeps_version_numbers_in_skill_names():
    matcher = JobMatcher()
    # A 1-5 digit inside a skill name (Vue3, Angular2) must not be read as the
    # score, nor truncate the name.
    parsed = matcher.parse_job_skills("Vue3 , 4 , AI | Python3 %> 5 | Angular2 , 3")
    assert parsed == [("Vue3", 4), ("Python3", 5), ("Angular2", 3)]


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


def test_top_skill_gaps_aggregates_and_ranks_missing_skills():
    matcher = JobMatcher()
    resume_skills = [{"skill_name": "Python", "score": 5}]
    jobs = [
        {"id": "a", "skill_tags_raw": "Python , 5 , AI | Kubernetes , 4 , AI | Go , 3 , AI"},
        {"id": "b", "skill_tags_raw": "Python , 5 , AI | Kubernetes , 4 , AI"},
        {"id": "c", "skill_tags_raw": "Python , 5 , AI | Docker , 4 , AI"},
    ]

    gaps = matcher.top_skill_gaps(matcher.match_jobs(resume_skills, jobs))

    # Kubernetes is missing in two jobs, so it is the top gap to close first;
    # Docker and Go each appear once and tie-break by (normalized) name.
    assert gaps[0] == {"skill": "Kubernetes", "job_count": 2}
    assert [g["skill"] for g in gaps] == ["Kubernetes", "Docker", "Go"]


def test_top_skill_gaps_respects_limit():
    matcher = JobMatcher()
    jobs = [{"id": "a", "skill_tags_raw": "Kubernetes , 4 , AI | Go , 3 , AI | Docker , 3 , AI"}]

    gaps = matcher.top_skill_gaps(matcher.match_jobs([], jobs), limit=2)

    assert len(gaps) == 2


def test_single_letter_skill_does_not_fuzzy_match_inside_a_word():
    # A one-letter job skill like "R" (the R language) must not fuzzy-match
    # every resume skill that merely contains that letter ("React"), or the
    # candidate looks qualified for a skill they don't have. It surfaces as a
    # gap unless the resume lists "R" exactly.
    matcher = JobMatcher()
    result = matcher._calculate_match({"react": 4, "scala": 3}, [("R", 3)])
    assert result["matched_skills"] == []
    assert result["missing_skills"] == ["R"]

    # Exact single-letter matches still work.
    exact = matcher._calculate_match({"r": 5}, [("R", 3)])
    assert exact["matched_skills"] == ["R"]


def test_two_letter_skill_still_fuzzy_matches_as_before():
    # The >= 2 char guard must not regress real two-letter fuzzy matches.
    matcher = JobMatcher()
    result = matcher._calculate_match({"advanced-ml": 8}, [("ml", 4)])
    assert result["matched_skills"] == ["ml"]


def test_fuzzy_match_picks_highest_scoring_resume_skill_not_first():
    # When a job skill fuzzy-matches several resume skills, the score must come
    # from the best (highest-scoring) one, not whichever the dict yields first.
    matcher = JobMatcher()
    resume_skills = {"ml-basics": 2, "advanced-ml": 8}
    result = matcher._calculate_match(resume_skills, [("ml", 4)])
    detail = result["details"]["matched_skills_detail"]
    assert len(detail) == 1
    assert detail[0]["resume_skill_name"] == "advanced-ml"
    assert detail[0]["resume_score"] == 8
