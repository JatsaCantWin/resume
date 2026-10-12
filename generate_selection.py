#!/usr/bin/env python3

import argparse
import sys
import json
from dataclasses import dataclass
from pathlib import Path

import dspy
import yaml


@dataclass
class ExperienceSelection:
    id: str
    bullets: list[str]


@dataclass
class ProjectSelection:
    id: str
    bullets: list[str]


@dataclass
class SkillSelection:
    technical: list[str]
    language: list[str]
    interests: list[str]


@dataclass
class ResumeSelection:
    education: list[str]
    experience: list[ExperienceSelection]
    projects: list[ProjectSelection]
    certifications: list[str]
    publications: list[str]
    awards: list[str]
    skills: SkillSelection


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def dump_yaml(data: dict) -> str:
    return yaml.safe_dump(
        data,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )


class ResumeSelector(dspy.Signature):
    job_listing: str = dspy.InputField(desc="Complete job listing.")

    master_resume: str = dspy.InputField(
        desc=(
            "Complete master resume YAML. This is the source of truth "
            "for the candidate's experience."
        )
    )

    selection_catalog: str = dspy.InputField(
        desc=(
            "Canonical catalog of selectable IDs and their descriptions. "
            "ALWAYS use the canonical `id` values from this catalog."
        )
    )

    selection_json: str = dspy.OutputField(
        desc="""
Return ONLY valid JSON.

Every selected item MUST use its canonical `id` from selection_catalog.

NEVER put a human-readable name, description, or bullet text into an `id`
or `bullets` field.

For example, if the catalog contains:

{
  "id": "dell-ci-cd-scale",
  "text": "Built CI/CD integration across an around 150 repository wide organization"
}

then the output MUST contain:

{
  "bullets": ["dell-ci-cd-scale"]
}

NOT:

{
  "bullets": [
    "Built CI/CD integration across an around 150 repository wide organization"
  ]
}

Required structure:

{
  "education": ["education-id"],
  "experience": [
    {
      "id": "experience-id",
      "bullets": ["bullet-id"]
    }
  ],
  "projects": [
    {
      "id": "project-id",
      "bullets": ["bullet-id"]
    }
  ],
  "certifications": ["certification-id"],
  "publications": ["publication-id"],
  "awards": ["award-id"],
  "skills": {
    "technical": ["skill-id"],
    "language": ["skill-id"],
    "interests": ["skill-id"]
  }
}

Use empty arrays when nothing should be selected.
"""
    )

    match_score: int = dspy.OutputField(desc="An integer from 0 to 10.")

    missing_experience: str = dspy.OutputField(
        desc=(
            "Concrete job requirements that are not demonstrated "
            "by the master resume."
        )
    )

    forgotten_experience: str = dspy.OutputField(
        desc=(
            "Things the candidate might have done but has not recorded. "
            "Phrase these as possibilities, not facts."
        )
    )

    selection_reasoning: str = dspy.OutputField(
        desc=(
            "Brief explanation of how the selected content balances "
            "job relevance, employment-history coverage, and recruiter "
            "readability."
        )
    )


def index_items(items) -> dict[str, dict]:
    return {
        item["id"]: item for item in items if isinstance(item, dict) and "id" in item
    }


def build_indexes(master: dict) -> dict:
    experience = index_items(master.get("experience", []))

    projects = index_items(master.get("projects", []))

    experience_bullets = {
        experience_id: index_items(experience_item.get("bullets", []))
        for experience_id, experience_item in experience.items()
    }

    project_bullets = {
        project_id: index_items(project_item.get("bullets", []))
        for project_id, project_item in projects.items()
    }

    skills = master.get("skills", {})

    return {
        "education": index_items(master.get("education", [])),
        "experience": experience,
        "experience_bullets": experience_bullets,
        "projects": projects,
        "project_bullets": project_bullets,
        "certifications": index_items(master.get("certifications", [])),
        "publications": index_items(master.get("publications", [])),
        "awards": index_items(master.get("awards", [])),
        "skills": {
            category: index_items(skills.get(category, []))
            for category in (
                "technical",
                "language",
                "interests",
            )
        },
    }


def build_selection_catalog(master: dict) -> dict:
    """
    Build a compact catalog specifically for the LLM.
    """

    catalog = {
        "education": [],
        "experience": [],
        "projects": [],
        "certifications": [],
        "publications": [],
        "awards": [],
        "skills": {
            "technical": [],
            "language": [],
            "interests": [],
        },
    }

    for item in master.get("education", []):
        catalog["education"].append(
            {
                "id": item["id"],
                "description": (
                    f'{item.get("institution", "")} — ' f'{item.get("degree", "")}'
                ),
            }
        )

    for item in master.get("experience", []):
        catalog["experience"].append(
            {
                "id": item["id"],
                "description": (
                    f'{item.get("company", "")} — ' f'{item.get("role", "")}'
                ),
                "bullets": [
                    {
                        "id": bullet["id"],
                        "text": bullet.get("text", ""),
                        "tags": bullet.get("tags", []),
                    }
                    for bullet in item.get("bullets", [])
                ],
            }
        )

    for item in master.get("projects", []):
        catalog["projects"].append(
            {
                "id": item["id"],
                "description": item.get("name", ""),
                "bullets": [
                    {
                        "id": bullet["id"],
                        "text": bullet.get("text", ""),
                        "tags": bullet.get("tags", []),
                    }
                    for bullet in item.get("bullets", [])
                ],
            }
        )

    for category in (
        "certifications",
        "publications",
        "awards",
    ):
        for item in master.get(category, []):
            catalog[category].append(
                {
                    "id": item["id"],
                    "description": (item.get("name") or item.get("title") or ""),
                }
            )

    for category in (
        "technical",
        "language",
        "interests",
    ):
        for item in master.get("skills", {}).get(
            category,
            [],
        ):
            catalog["skills"][category].append(
                {
                    "id": item["id"],
                    "name": item.get("name", ""),
                    "level": item.get("level"),
                    "tags": item.get("tags", []),
                }
            )

    return catalog


def parse_selection(raw: str) -> ResumeSelection:
    """
    Parse the JSON produced by DSPy into ordinary Python structures.
    """

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "DSPy returned invalid JSON for selection:\n\n" + raw
        ) from exc

    if not isinstance(data, dict):
        raise RuntimeError("DSPy selection JSON must be an object.")

    skills = data.get("skills", {})

    if not isinstance(skills, dict):
        raise RuntimeError("DSPy returned `skills` in an invalid format.")

    try:
        experience = [
            ExperienceSelection(
                id=item["id"],
                bullets=item.get("bullets", []),
            )
            for item in data.get("experience", [])
        ]

        projects = [
            ProjectSelection(
                id=item["id"],
                bullets=item.get("bullets", []),
            )
            for item in data.get("projects", [])
        ]

        return ResumeSelection(
            education=data.get("education", []),
            experience=experience,
            projects=projects,
            certifications=data.get(
                "certifications",
                [],
            ),
            publications=data.get(
                "publications",
                [],
            ),
            awards=data.get(
                "awards",
                [],
            ),
            skills=SkillSelection(
                technical=skills.get(
                    "technical",
                    [],
                ),
                language=skills.get(
                    "language",
                    [],
                ),
                interests=skills.get(
                    "interests",
                    [],
                ),
            ),
        )

    except (KeyError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            "DSPy returned JSON with an unexpected structure:\n\n" + raw
        ) from exc


def resolve_value(
    value: str,
    available: dict[str, dict],
) -> str:
    """
    Resolve a model-produced value.

    Ideally the model returns an ID.

    If it accidentally returns the item's name or text, resolve that value
    deterministically back to the canonical ID.

    If nothing matches, leave the value untouched so normal validation can
    report it clearly.
    """

    if value in available:
        return value

    for item_id, item in available.items():
        if item.get("id") == value:
            return item_id

        if item.get("name") == value:
            return item_id

        if item.get("text") == value:
            return item_id

        if item.get("title") == value:
            return item_id

    return value


def normalize_selection(
    selection: ResumeSelection,
    master: dict,
) -> ResumeSelection:
    """
    Recover from common LLM mistakes where the model outputs human-readable
    text instead of canonical IDs.
    """

    indexes = build_indexes(master)

    selection.education = [
        resolve_value(
            value,
            indexes["education"],
        )
        for value in selection.education
    ]

    selection.certifications = [
        resolve_value(
            value,
            indexes["certifications"],
        )
        for value in selection.certifications
    ]

    selection.publications = [
        resolve_value(
            value,
            indexes["publications"],
        )
        for value in selection.publications
    ]

    selection.awards = [
        resolve_value(
            value,
            indexes["awards"],
        )
        for value in selection.awards
    ]

    for experience in selection.experience:
        experience.id = resolve_value(
            experience.id,
            indexes["experience"],
        )

        available_bullets = indexes["experience_bullets"].get(
            experience.id,
            {},
        )

        experience.bullets = [
            resolve_value(
                bullet,
                available_bullets,
            )
            for bullet in experience.bullets
        ]

    for project in selection.projects:
        project.id = resolve_value(
            project.id,
            indexes["projects"],
        )

        available_bullets = indexes["project_bullets"].get(
            project.id,
            {},
        )

        project.bullets = [
            resolve_value(
                bullet,
                available_bullets,
            )
            for bullet in project.bullets
        ]

    for category in (
        "technical",
        "language",
        "interests",
    ):
        available = indexes["skills"][category]

        values = getattr(
            selection.skills,
            category,
        )

        setattr(
            selection.skills,
            category,
            [
                resolve_value(
                    value,
                    available,
                )
                for value in values
            ],
        )

    return selection


def validate_ids(
    selection: ResumeSelection,
    master: dict,
) -> list[str]:
    indexes = build_indexes(master)
    errors = []

    def check_ids(
        values,
        available,
        field,
    ):
        for value in values:
            if value not in available:
                errors.append(f"{field}: unknown ID '{value}'")

    check_ids(
        selection.education,
        indexes["education"],
        "education",
    )

    check_ids(
        selection.certifications,
        indexes["certifications"],
        "certifications",
    )

    check_ids(
        selection.publications,
        indexes["publications"],
        "publications",
    )

    check_ids(
        selection.awards,
        indexes["awards"],
        "awards",
    )

    for experience in selection.experience:
        experience_id = experience.id

        if experience_id not in indexes["experience"]:
            errors.append(f"experience: unknown ID '{experience_id}'")
            continue

        check_ids(
            experience.bullets,
            indexes["experience_bullets"].get(
                experience_id,
                {},
            ),
            f"experience.{experience_id}.bullets",
        )

    for project in selection.projects:
        project_id = project.id

        if project_id not in indexes["projects"]:
            errors.append(f"projects: unknown ID '{project_id}'")
            continue

        check_ids(
            project.bullets,
            indexes["project_bullets"].get(
                project_id,
                {},
            ),
            f"projects.{project_id}.bullets",
        )

    for category in (
        "technical",
        "language",
        "interests",
    ):
        check_ids(
            getattr(
                selection.skills,
                category,
            ),
            indexes["skills"][category],
            f"skills.{category}",
        )

    return errors


def find_omitted_employers(
    selection: ResumeSelection,
    master: dict,
) -> list[dict]:
    """
    Find employers completely omitted by the model.
    """

    selected_ids = {item.id for item in selection.experience}

    return [
        item for item in master.get("experience", []) if item["id"] not in selected_ids
    ]


def selection_to_dict(
    selection: ResumeSelection,
) -> dict:
    """
    Produce exactly the schema expected by resolve_selection().
    """

    return {
        "education": selection.education,
        "experience": [
            {
                "id": item.id,
                "bullets": item.bullets,
            }
            for item in selection.experience
        ],
        "projects": [
            {
                "id": item.id,
                "bullets": item.bullets,
            }
            for item in selection.projects
        ],
        "certifications": selection.certifications,
        "publications": selection.publications,
        "awards": selection.awards,
        "skills": {
            "technical": selection.skills.technical,
            "language": selection.skills.language,
            "interests": selection.skills.interests,
        },
    }


def build_report(
    match_score: int,
    missing_experience: str,
    forgotten_experience: str,
    selection_reasoning: str,
    omitted_employers: list[dict],
) -> str:
    omitted_section = "None."

    if omitted_employers:
        omitted_section = "\n".join(
            f"- {item.get('company', item['id'])} " f"({item['id']})"
            for item in omitted_employers
        )

    return f"""# Resume Match Analysis

## Match score

{match_score}/10

## Selection reasoning

{selection_reasoning.strip()}

## Missing experience

{missing_experience.strip() or "None identified."}

## Potentially forgotten experience

{forgotten_experience.strip() or "None identified."}

## Employers omitted from selection

{omitted_section}
"""


def configure_dspy(model: str):
    dspy.configure(lm=dspy.LM(model))


def main():
    parser = argparse.ArgumentParser(
        description=("Generate a job-specific resume selection using DSPy.")
    )

    parser.add_argument(
        "master",
        type=Path,
        help="Path to the master resume YAML.",
    )

    parser.add_argument(
        "output",
        type=Path,
        help="Path for the generated selection YAML.",
    )

    parser.add_argument(
        "--report",
        type=Path,
        help=("Optional path for the generated match analysis report."),
    )

    parser.add_argument(
        "--model",
        default="openai/gpt-5.6",
        help="DSPy model name.",
    )

    args = parser.parse_args()

    job_listing = sys.stdin.read()

    master = load_yaml(args.master)
    master_yaml = dump_yaml(master)

    selection_catalog = build_selection_catalog(master)
    selection_catalog_yaml = dump_yaml(selection_catalog)

    configure_dspy(args.model)

    selector = dspy.Predict(ResumeSelector)

    result = selector(
        job_listing=job_listing,
        master_resume=master_yaml,
        selection_catalog=selection_catalog_yaml,
    )

    selection = parse_selection(result.selection_json)

    selection = normalize_selection(
        selection,
        master,
    )

    errors = validate_ids(
        selection,
        master,
    )

    if errors:
        raise RuntimeError(
            "DSPy selected IDs that do not exist in the master resume:\n\n"
            + "\n".join(f"- {error}" for error in errors)
        )

    try:
        match_score = int(result.match_score)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            f"Invalid match score returned by DSPy: " f"{result.match_score!r}"
        ) from exc

    if not 0 <= match_score <= 10:
        raise RuntimeError(
            f"Match score must be between 0 and 10, " f"got {match_score}"
        )

    omitted_employers = find_omitted_employers(
        selection,
        master,
    )

    if omitted_employers:
        print("\nWarning: the model completely omitted these employers:")

        for employer in omitted_employers:
            print(f"  - {employer.get('company', employer['id'])}")

    selection_data = selection_to_dict(selection)

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    args.output.write_text(
        dump_yaml(selection_data),
        encoding="utf-8",
    )

    report = build_report(
        match_score=match_score,
        missing_experience=result.missing_experience,
        forgotten_experience=result.forgotten_experience,
        selection_reasoning=result.selection_reasoning,
        omitted_employers=omitted_employers,
    )

    if args.report:
        args.report.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        args.report.write_text(
            report,
            encoding="utf-8",
        )

    else:
        print()
        print(report)

    print(f"Generated selection: {args.output}")

    if args.report:
        print(f"Generated report: {args.report}")


if __name__ == "__main__":
    main()
