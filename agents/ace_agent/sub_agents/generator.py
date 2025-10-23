from google.adk.agents import Agent
from pydantic import BaseModel, Field

from config import Config

config = Config()


# -------------------------
# 1) Generator output schema
# -------------------------
class GeneratorOutput(BaseModel):
    reasoning: list[str] = Field(
        description="Provide step-by-step reasoning process in the format of [step-by-step thought process / reasoning process / detailed analysis and calculation]"
    )
    bullet_ids: list[str] = Field(
        default_factory=list, description="List of playbook bullet IDs referenced"
    )
    final_answer: str = Field(description="Concise final answer")


# ============================================
# Generator: Generate answers and traces using playbook
# ============================================
generator = Agent(
    name="Generator",
    model=config.generator_model,
    description="Solve problems by referencing the playbook and return structured final answers.",
    instruction="""
Your task is to answer user queries while providing structured step-by-step reasoning and the bullet IDs you used.

Input:
- User Query: {user_query}
- Current Playbook: {app:playbook}

【Required Guidelines】

1. Carefully read the playbook and apply relevant strategies, formulas, and insights
   - Check all bullet points in the playbook
   - Understand the context and application conditions of each strategy

2. Carefully examine common failures (anti-patterns) listed in the playbook and avoid them
   - Present specific alternatives or best practices

3. Show the reasoning process step by step
   - Clearly indicate which bullets you referenced at each stage
   - Structure so that the logic flow is clear

4. Create thorough but concise analysis
   - Include only essential information, but include all central evidence
   - Avoid unnecessary repetition

5. Review calculations and logic before providing the final answer
   - Confirm that all referenced bullet_ids were actually used
   - Check for logical contradictions
   - Double-check that you haven't missed any relevant playbook bullets

【Output Rules】
- reasoning: Step-by-step thought process (step-by-step chain of thought), detailed analysis and calculations
- bullet_ids: List of referenced playbook bullet IDs
- final_answer: Clear and verified final answer
""",
    include_contents="none",  # Focus on state value injection
    output_schema=GeneratorOutput,  # Structure output
    output_key="generator_output",  # Save to session.state['generator_output']
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
)
