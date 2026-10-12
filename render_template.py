#!/usr/bin/env python3

from pathlib import Path
import argparse

import yaml
from jinja2 import Environment, FileSystemLoader


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def index_by_id(items):
    return {item["id"]: item for item in items}


def resolve_items(master_items, selected_ids):
    items_by_id = index_by_id(master_items)
    return [items_by_id[item_id] for item_id in selected_ids]


def resolve_selection(master, selection):
    result = {}

    result["personal"] = master["personal"]

    result["education"] = resolve_items(
        master.get("education", []),
        selection.get("education", []),
    )

    experience_by_id = index_by_id(master.get("experience", []))

    result["experience"] = []

    for selected_experience in selection.get("experience", []):
        experience_id = selected_experience["id"]

        experience = experience_by_id[experience_id].copy()

        bullets_by_id = index_by_id(experience.get("bullets", []))

        experience["bullets"] = [
            bullets_by_id[bullet_id]
            for bullet_id in selected_experience.get("bullets", [])
        ]

        result["experience"].append(experience)

    projects_by_id = index_by_id(master.get("projects", []))

    result["projects"] = []

    for selected_project in selection.get("projects", []):
        project_id = selected_project["id"]

        project = projects_by_id[project_id].copy()

        bullets_by_id = index_by_id(project.get("bullets", []))

        project["bullets"] = [
            bullets_by_id[bullet_id]
            for bullet_id in selected_project.get("bullets", [])
        ]

        result["projects"].append(project)

    result["certifications"] = resolve_items(
        master.get("certifications", []),
        selection.get("certifications", []),
    )

    result["publications"] = resolve_items(
        master.get("publications", []),
        selection.get("publications", []),
    )

    result["awards"] = resolve_items(
        master.get("awards", []),
        selection.get("awards", []),
    )

    master_skills = master.get("skills", {})
    selected_skills = selection.get("skills", {})

    result["skills"] = {}

    for category in ["technical", "language", "interests"]:
        result["skills"][category] = resolve_items(
            master_skills.get(category, []),
            selected_skills.get(category, []),
        )

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Render a complete resume LaTeX document from YAML data."
    )

    parser.add_argument(
        "master",
        type=Path,
        help="Path to the master YAML file",
    )

    parser.add_argument(
        "selection",
        type=Path,
        help="Path to the selection YAML file",
    )

    parser.add_argument(
        "template",
        type=Path,
        help="Path to the Jinja2 LaTeX template",
    )

    parser.add_argument(
        "output",
        type=Path,
        help="Path to the generated LaTeX file",
    )

    args = parser.parse_args()

    master = load_yaml(args.master)
    selection = load_yaml(args.selection)

    context = resolve_selection(
        master,
        selection,
    )

    env = Environment(
        loader=FileSystemLoader(str(args.template.parent)),
        variable_start_string="<<",
        variable_end_string=">>",
        block_start_string="<%",
        block_end_string="%>",
        comment_start_string="<#",
        comment_end_string="#>",
        trim_blocks=True,
        lstrip_blocks=True,
    )

    template = env.get_template(args.template.name)

    rendered = template.render(**context)

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    args.output.write_text(
        rendered,
        encoding="utf-8",
    )

    print(f"Generated: {args.output}")


if __name__ == "__main__":
    main()
