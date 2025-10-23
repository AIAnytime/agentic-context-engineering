from typing import AsyncGenerator

from google.adk.agents import Agent, BaseAgent, SequentialAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai.types import Part, UserContent

from agents.ace_agent.schemas import DeltaBatch, Playbook
from config import Config

config = Config()

# ============================================
# Curator: Expert in curating playbooks
# ============================================
curator_ = Agent(
    name="Curator",
    model=config.curator_model,
    description="Expert in curating playbooks.",
    instruction="""You are an expert in curating playbooks.

Considering the existing playbook and reflections from previous attempts:
- Identify only new insights, strategies, and failures that are **missing** from the current playbook
- You can **improve existing bullets with better content** or **remove erroneous/duplicate items**
- Avoid duplication - if similar advice already exists, add only new content that perfectly complements the existing playbook
- Do not regenerate the entire playbook - provide only necessary additions/modifications/deletions
- Focus on quality over quantity - a focused and organized playbook is better than a comprehensive one
- Each change must be specific and justified

Input:
- User Query: {user_query}
- Reflector Results: {reflector_output}
- Current Playbook: {app:playbook}

CRITICAL: You must respond with ONLY valid JSON. No markdown, no explanations, no code blocks.

Response format (maximum 3 operations per response):
{
  "reasoning": "Brief explanation (max 200 characters)",
  "operations": [
    {
      "type": "ADD",
      "section": "general",
      "content": "Specific actionable advice (max 150 characters)"
    },
    {
      "type": "UPDATE", 
      "bullet_id": "existing-id",
      "content": "Improved content (max 150 characters)"
    },
    {
      "type": "REMOVE",
      "bullet_id": "id-to-remove"
    }
  ]
}

Rules:
- Maximum 3 operations per response
- Keep content concise and actionable
- Ensure all JSON strings are properly escaped
- If no changes needed, return: {"reasoning": "No changes needed", "operations": []}""",
    include_contents="none",
    output_schema=DeltaBatch,
    output_key="curator_output",
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
)


class PlaybookUpdater(BaseAgent):
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        curator_output: dict | None = state.get("curator_output")
        delta_batch = DeltaBatch.from_dict(curator_output)

        playbook: dict | None = state.get("app:playbook")
        playbook: Playbook = Playbook.from_dict(playbook)
        playbook.apply_delta(delta_batch)

        state_changes = {"app:playbook": playbook.to_dict()}

        # Emit event (display text)
        ops = delta_batch.operations
        op_lines = []
        for op in ops:
            bullet_ref = f"[{op.bullet_id}]" if op.bullet_id else ""
            content_text = op.content or "(no content)"
            op_lines.append(
                f"- {op.type:6} {op.section:12} {bullet_ref:15} {content_text}"
            )
        pretty = "\n".join(op_lines) or "(no changes)"
        content = UserContent(
            parts=[Part(text=f"[Curator] Playbook Changes:\n{pretty}")]
        )
        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            content=content,
            actions=EventActions(state_delta=state_changes),
        )


playbook_updater = PlaybookUpdater(
    name="playbook_updater", description="Updates the playbook."
)


curator = SequentialAgent(
    name="Curator",
    description="Execute Curator and PlaybookUpdater sequentially.",
    sub_agents=[curator_, playbook_updater],
)
