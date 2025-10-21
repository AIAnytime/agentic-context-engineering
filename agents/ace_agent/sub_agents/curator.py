from typing import AsyncGenerator

from google.adk.agents import Agent, BaseAgent, SequentialAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai.types import Part, UserContent

from agents.ace_agent.schemas import DeltaBatch, Playbook
from config import Config

config = Config()

# ============================================
# キュレーター：プレイブックをキュレーションする専門家
# ============================================
curator_ = Agent(
    name="Curator",
    model=config.curator_model,
    description="プレイブックをキュレーションする専門家です。",
    instruction="""あなたはプレイブックをキュレーションする専門家です。

既存のプレイブックと以前の試みの考察（reflection）を検討して：
- 現在のプレイブックに**不足している**新しい洞察、戦略、失敗のみを識別してください
- **既存のbulletをより良い内容に改善**したり、**エラー/重複した項目を削除**できます
- 重複を避けてください - 類似したアドバイスが既に存在する場合、既存のプレイブックを完璧に補完する新しい内容のみを追加してください
- プレイブック全体を再生成しないでください - 必要な追加/修正/削除項目のみを提供してください
- 量より質に集中してください - 集中して整理されたプレイブックが包括的なものより優れています
- 各変更は具体的で正当化される必要があります

入力：
- ユーザークエリ: {user_query}
- Reflectorの結果: {reflector_output}
- 現在のPlaybook: {app:playbook}

レスポンスは次の形式の純粋なJSONオブジェクトで記述してください：
{
  "reasoning": "変更が必要な理由についての簡単な説明",
  "operations": [
    {
      "type": "ADD",
      "section": "general",
      "content": "追加する具体的で実行可能なアドバイス"
    },
    {
      "type": "UPDATE",
      "bullet_id": "strategy-00001",
      "content": "既存のbulletをこのように改善された内容に修正します"
    },
    {
      "type": "REMOVE",
      "bullet_id": "mistakes-00002"
    }
  ]
}

新しい変更がない場合、operationsフィールドに空配列を返してください。
""",
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

        # 이벤트 방출(표시용 텍스트)
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
            parts=[Part(text=f"[Curator] プレイブック変更内容:\n{pretty}")]
        )
        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            content=content,
            actions=EventActions(state_delta=state_changes),
        )


playbook_updater = PlaybookUpdater(
    name="playbook_updater", description="プレイブックを更新します。"
)


curator = SequentialAgent(
    name="Curator",
    description="CuratorとPlaybookUpdaterを順次実行します。",
    sub_agents=[curator_, playbook_updater],
)
