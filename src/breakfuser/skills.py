"""Progressive skill disclosure registry."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


class Skill(BaseModel):
    name: str
    description: str
    body: str


class SkillRegistry:
    def __init__(self, skills: list[Skill] | None = None) -> None:
        self.skills = {skill.name: skill for skill in skills or []}

    @classmethod
    def from_directory(cls, root: str) -> SkillRegistry:
        skills: list[Skill] = []
        for path in Path(root).glob("*/SKILL.md"):
            lines = path.read_text().splitlines()
            description = next(
                (
                    line.removeprefix("description:").strip()
                    for line in lines
                    if line.startswith("description:")
                ),
                path.parent.name,
            )
            skills.append(
                Skill(name=path.parent.name, description=description, body=path.read_text())
            )
        return cls(skills)

    def base_prompt(self) -> str:
        return "\n".join(f"- {skill.name}: {skill.description}" for skill in self.skills.values())

    def load(self, name: str) -> str:
        if name not in self.skills:
            raise KeyError(f"Unknown skill: {name}")
        return self.skills[name].body
