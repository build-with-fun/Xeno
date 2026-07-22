import os
import sys
import json
import shutil
import hashlib
import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Any

import yaml
from fastmcp import FastMCP

SKILLS_DIR = Path(os.environ.get("XENO_SKILLS_DIR", str(Path(__file__).resolve().parent.parent.parent.parent / "skills")))
SKILLS_DIR.mkdir(parents=True, exist_ok=True)

mcp = FastMCP("Skill Creation Server")


@dataclass
class SkillPackage:
    name: str
    path: Path
    manifest: dict = field(default_factory=dict)


def _load_manifest(skill_path: Path) -> dict:
    manifest_path = skill_path / "skill.json"
    if manifest_path.exists():
        return json.loads(manifest_path.read_text())
    return {}


def _save_manifest(skill_path: Path, manifest: dict):
    manifest_path = skill_path / "skill.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))


def compile_skill_package(
    skills_dir: Path,
    skill_name: str,
    description: str,
    observations: str = "",
    playbook: str = "",
    examples: str = "",
    tests: str = "",
    failures: str = "",
    source_task_id: str = "",
    confidence: float = 0.55,
    overwrite: bool = False,
) -> SkillPackage:
    skill_path = skills_dir / skill_name
    if skill_path.exists() and not overwrite:
        raise FileExistsError(f"Skill '{skill_name}' already exists. Use overwrite=True to replace.")

    skill_path.mkdir(parents=True, exist_ok=True)

    def _parse_json_list(raw: str) -> list:
        if not raw or not raw.strip():
            return []
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, list) else [parsed]
        except json.JSONDecodeError:
            return [item.strip() for item in raw.split("\n") if item.strip()]

    observations_list = _parse_json_list(observations)
    playbook_list = _parse_json_list(playbook)
    examples_list = _parse_json_list(examples)
    tests_list = _parse_json_list(tests)
    failures_list = _parse_json_list(failures)

    md_lines = [
        f"# {skill_name}\n",
        f"## Description\n{description}\n",
    ]
    if observations_list:
        md_lines.append("## Observations\n" + "\n".join(f"- {o}" for o in observations_list) + "\n")
    if playbook_list:
        md_lines.append("## Playbook\n" + "\n".join(f"{i+1}. {p}" for i, p in enumerate(playbook_list)) + "\n")
    if examples_list:
        md_lines.append("## Examples\n" + "\n".join(f"```\n{e}\n```" for e in examples_list) + "\n")
    if tests_list:
        md_lines.append("## Tests\n" + "\n".join(f"- {t}" for t in tests_list) + "\n")
    if failures_list:
        md_lines.append("## Known Failures\n" + "\n".join(f"- {f}" for f in failures_list) + "\n")

    (skill_path / "SKILL.md").write_text("\n".join(md_lines), encoding="utf-8")

    frontmatter = {"name": skill_name, "description": description}
    yaml_fm = "---\n" + yaml.dump(frontmatter, default_flow_style=False) + "---\n\n"
    (skill_path / "SKILL.md").write_text(yaml_fm + "\n".join(md_lines), encoding="utf-8")

    manifest = {
        "name": skill_name,
        "description": description,
        "confidence": confidence,
        "uses": 0,
        "successes": 0,
        "failures": 0,
        "created_at": datetime.datetime.now().isoformat(),
        "source_task_id": source_task_id,
    }
    _save_manifest(skill_path, manifest)

    data_path = skill_path / "data"
    data_path.mkdir(exist_ok=True)
    (data_path / "observations.json").write_text(json.dumps(observations_list, indent=2))
    (data_path / "playbook.json").write_text(json.dumps(playbook_list, indent=2))
    (data_path / "examples.json").write_text(json.dumps(examples_list, indent=2))
    (data_path / "tests.json").write_text(json.dumps(tests_list, indent=2))
    (data_path / "failures.json").write_text(json.dumps(failures_list, indent=2))

    return SkillPackage(name=skill_name, path=skill_path, manifest=manifest)


def list_skill_packages(skills_dir: Path) -> list:
    packages = []
    if not skills_dir.exists():
        return packages
    for item in sorted(skills_dir.iterdir()):
        if item.is_dir() and (item / "skill.json").exists():
            manifest = _load_manifest(item)
            packages.append({
                "name": manifest.get("name", item.name),
                "path": str(item),
                "confidence": manifest.get("confidence", 0.0),
                "uses": manifest.get("uses", 0),
            })
    return packages


def record_skill_outcome(
    skills_dir: Path,
    skill_name: str,
    success: bool,
    note: str = "",
    score_delta: float = 0.0,
) -> SkillPackage:
    skill_path = skills_dir / skill_name
    if not skill_path.exists():
        raise FileNotFoundError(f"Skill '{skill_name}' not found")

    manifest = _load_manifest(skill_path)
    manifest["uses"] = manifest.get("uses", 0) + 1
    if success:
        manifest["successes"] = manifest.get("successes", 0) + 1
        manifest["confidence"] = min(1.0, manifest.get("confidence", 0.5) + score_delta)
    else:
        manifest["failures"] = manifest.get("failures", 0) + 1
        manifest["confidence"] = max(0.0, manifest.get("confidence", 0.5) - abs(score_delta))

    manifest["last_used"] = datetime.datetime.now().isoformat()
    if note:
        outcomes = manifest.get("outcomes", [])
        outcomes.append({"success": success, "note": note, "timestamp": datetime.datetime.now().isoformat()})
        manifest["outcomes"] = outcomes[-50:]

    _save_manifest(skill_path, manifest)
    return SkillPackage(name=skill_name, path=skill_path, manifest=manifest)


@mcp.tool()
def create_skill(skill_name: str, description: str, md_text: str) -> str:
    """
    Creates a new persistent skill for the agent to use in future tasks.
    skill_name: A short, lowercase-kebab-case name (e.g. 'react-performance').
    description: A concise description of the skill (max 1000 characters).
    md_text: The massive, highly detailed markdown body of the skill. Must be highly advanced,
             containing rules, constraints, and instructions.
    """
    if len(description) > 1000:
        return "Error: Description must be less than 1000 characters."

    line_count = len(md_text.splitlines())
    if line_count < 50:
        return f"Warning: Skill body seems too short ({line_count} lines). The system expects highly advanced, comprehensive skills (ideally 500+ lines). Skill was saved, but consider expanding it in the future."
    if line_count > 1000:
        return f"Error: Skill body is too massive ({line_count} lines). Max allowed is 1000 lines. Please condense it."

    skill_folder = SKILLS_DIR / skill_name

    if skill_folder.exists():
        return f"Error: Skill '{skill_name}' already exists."

    try:
        os.makedirs(skill_folder, exist_ok=True)
        skill_file = skill_folder / "SKILL.md"

        frontmatter = {
            "name": skill_name,
            "description": description
        }

        yaml_frontmatter = "---\n" + yaml.dump(frontmatter, default_flow_style=False) + "---\n\n"

        with open(skill_file, "w", encoding="utf-8") as f:
            f.write(yaml_frontmatter + md_text)

        return f"Successfully created super-advanced skill '{skill_name}'! It will be automatically loaded in all future executions."
    except Exception as e:
        return f"Failed to create skill: {str(e)}"

@mcp.tool()
def update_skill(skill_name: str, description: str, md_text: str) -> str:
    """
    Updates an existing skill's content and description.
    """
    if len(description) > 1000:
        return "Error: Description must be less than 1000 characters."

    skill_folder = SKILLS_DIR / skill_name
    if not skill_folder.exists():
        return f"Error: Skill '{skill_name}' does not exist. Use create_skill instead."

    try:
        skill_file = skill_folder / "SKILL.md"
        frontmatter = {
            "name": skill_name,
            "description": description,
            "last_updated": datetime.datetime.now().isoformat()
        }
        yaml_frontmatter = "---\n" + yaml.dump(frontmatter, default_flow_style=False) + "---\n\n"
        with open(skill_file, "w", encoding="utf-8") as f:
            f.write(yaml_frontmatter + md_text)
        return f"Successfully updated skill '{skill_name}'."
    except Exception as e:
        return f"Failed to update skill: {str(e)}"

@mcp.tool()
def delete_skill(skill_name: str) -> str:
    """
    Deletes an existing skill completely.
    """
    skill_folder = SKILLS_DIR / skill_name
    if not skill_folder.exists():
        return f"Error: Skill '{skill_name}' does not exist."
    try:
        shutil.rmtree(skill_folder)
        return f"Successfully deleted skill '{skill_name}'."
    except Exception as e:
        return f"Failed to delete skill: {str(e)}"

@mcp.tool()
def compile_evolving_skill(
    skill_name: str,
    description: str,
    observations_json: str = "",
    playbook_json: str = "",
    examples_json: str = "",
    tests_json: str = "",
    failures_json: str = "",
    source_task_id: str = "",
    confidence: float = 0.55,
    overwrite: bool = False,
) -> str:
    """
    Compiles a self-evolving skill package.
    JSON inputs should be arrays. Plain text is accepted and stored as one item.
    The package includes SKILL.md, skill.json, examples, tests, failures, and outcomes.
    """
    try:
        package = compile_skill_package(
            SKILLS_DIR,
            skill_name=skill_name,
            description=description,
            observations=observations_json,
            playbook=playbook_json,
            examples=examples_json,
            tests=tests_json,
            failures=failures_json,
            source_task_id=source_task_id,
            confidence=confidence,
            overwrite=overwrite,
        )
        return json.dumps(
            {
                "status": "created",
                "name": package.name,
                "path": str(package.path.absolute()),
                "manifest": package.manifest,
            },
            indent=2,
        )
    except Exception as e:
        return f"Failed to compile evolving skill: {str(e)}"


@mcp.tool()
def list_evolving_skills() -> str:
    """Lists all self-evolving skill packages in this agent's skills directory."""
    try:
        return json.dumps(list_skill_packages(SKILLS_DIR), indent=2)
    except Exception as e:
        return f"Failed to list evolving skills: {str(e)}"


@mcp.tool()
def record_evolving_skill_outcome(
    skill_name: str,
    success: bool,
    note: str,
    score_delta: float = 0.0,
) -> str:
    """Records a skill usage outcome and adjusts the package confidence score."""
    try:
        package = record_skill_outcome(
            SKILLS_DIR,
            skill_name=skill_name,
            success=success,
            note=note,
            score_delta=score_delta,
        )
        return json.dumps(
            {
                "status": "recorded",
                "name": package.name,
                "confidence": package.manifest["confidence"],
                "uses": package.manifest["uses"],
                "successes": package.manifest["successes"],
                "failures": package.manifest["failures"],
            },
            indent=2,
        )
    except Exception as e:
        return f"Failed to record evolving skill outcome: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="stdio")
