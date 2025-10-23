from __future__ import annotations

from typing import AsyncGenerator

from google.adk.agents import BaseAgent, SequentialAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions

from .schemas.playbook import Playbook
from .sub_agents import curator, generator, reflector


class StateInitializer(BaseAgent):
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state

        state_changes = {}
        state_changes["user_query"] = ctx.user_content

        # Required state
        # Initialize app:playbook
        if "app:playbook" not in state:
            pb = Playbook()
            state_changes["app:playbook"] = pb.to_dict()

        # 🔹 ground_truth (optional)
        # If user doesn't provide, explicitly initialize with None
        if "ground_truth" not in state:
            state_changes["ground_truth"] = None

        actions_with_update = EventActions(state_delta=state_changes)

        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            actions=actions_with_update,
        )


state_initializer = StateInitializer(name="StateInitializer")

# ============================================
# Orchestration: Generator → Reflector → Curator → Check
# ============================================
ace_iteration = SequentialAgent(
    name="ACE_Iteration",
    sub_agents=[
        state_initializer,
        generator,
        reflector,
        curator,
    ],
    description="Execute one ACE cycle",
)

root_agent = ace_iteration
