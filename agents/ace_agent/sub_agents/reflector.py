from typing import AsyncGenerator, Literal

from google.adk.agents import Agent, BaseAgent, SequentialAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai.types import Part, UserContent
from pydantic import BaseModel, Field

from agents.ace_agent.schemas.playbook import Playbook
from config import Config

config = Config()


# -------------------------
# 2) Reflector output schema
# -------------------------
class BulletTag(BaseModel):
    id: str = Field(description="bullet-id")
    tag: Literal["helpful", "harmful", "neutral"] = Field(
        description="tag classification"
    )


class Reflection(BaseModel):
    reasoning: str = Field(description="Thought process and detailed analysis and calculations")
    error_identification: str = Field(
        description="What exactly was wrong in the reasoning"
    )
    root_cause_analysis: str = Field(
        description="Why did this error occur? Which concepts were misunderstood?"
    )
    correct_approach: str = Field(description="What should the model have done instead?")
    key_insight: str = Field(
        description="What strategy, formula, or principle should be remembered to avoid such errors?"
    )
    bullet_tags: list[BulletTag] = Field(
        default_factory=list,
        description="Bullet re-tagging (id and helpful/harmful/neutral tags)",
    )

    @classmethod
    def from_dict(cls, payload: dict) -> "Reflection":
        return cls.model_validate(payload)


# ============================================
# Reflector: Critically analyze errors/patterns
# ============================================
reflector_ = Agent(
    name="Reflector",
    model=config.reflector_model,
    description="Critically analyze errors and patterns to identify improvement points.",
    instruction="""
Your task is to carefully examine the generator's output, critically analyze it, and create a reflection (JSON).

Input:
- User query: {user_query}
- Generator output: {generator_output}
- Generator-referenced playbook bullet: {app:playbook}

【Required Analysis Steps】

1. Carefully analyze the model's reasoning trace to understand where errors occurred
   - Review the generator's entire reasoning
   - Check for leaps or contradictions in the logic flow

2. Identify specific error types: conceptual errors, calculation mistakes, strategy misuse, etc.
   - Clearly describe the characteristics of each error
   - Find the root causes behind surface-level errors

3. Provide actionable insights so the model doesn't make the same mistakes in the future
   - Present specific procedures or checklists
   - Derive generalizable principles

4. Evaluate each bullet point used by the generator
   - Tag each bullet_id as ['helpful', 'harmful', 'neutral']
   - helpful: bullets that helped with the correct answer
   - harmful: incorrect or misleading bullets that led to wrong answers
   - neutral: bullets that didn't affect the final result

【Output Rules】
- reasoning: Thought process that went through all 4 analysis steps above, detailed analysis and evidence
- error_identification: Specifically describe what exactly was wrong in the reasoning
- root_cause_analysis: What was the root cause of this error? Which concepts were misunderstood? Which strategies were misused?
- correct_approach: What should the generator have done instead? Present accurate steps and logic
- key_insight: Strategy, formula, principle, or checklist that should be remembered to avoid such errors
- bullet_tags: Tagging results for each bullet referenced by the generator (including id and 'helpful'/'harmful'/'neutral')
""",
    include_contents="none",
    output_schema=Reflection,
    output_key="reflector_output",  # session.state['reflector_output']
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
)


class TagBullet(BaseAgent):
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state

        reflector_output: dict | None = state.get("reflector_output")
        reflector_output: Reflection = Reflection.from_dict(reflector_output)
        bullet_tags = reflector_output.bullet_tags

        playbook: dict | None = state.get("app:playbook")
        playbook: Playbook = Playbook.from_dict(playbook)

        # Build display lines for tagging summary
        tag_lines: list[str] = []
        for bullet_tag in bullet_tags:
            bullet_id = bullet_tag.id
            tag = bullet_tag.tag
            playbook.update_bullet_tag(bullet_id=bullet_id, tag=tag)
            tag_lines.append(f"- [{bullet_id}] {tag}")

        state_changes = {"app:playbook": playbook.to_dict()}
        pretty = "\n".join(tag_lines) or "(no changes)"
        content = UserContent(
            parts=[Part(text=f"[Reflector] Bullet Tagging Results:\n{pretty}")]
        )
        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            content=content,
            actions=EventActions(state_delta=state_changes),
        )


tag_bullet = TagBullet(name="tag_bullet", description="Tags bullets.")

reflector = SequentialAgent(
    name="Reflector",
    description="Execute Reflector and TagBullet sequentially.",
    sub_agents=[reflector_, tag_bullet],
)
