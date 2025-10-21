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
# 2) リフレクター出力スキーマ
# -------------------------
class BulletTag(BaseModel):
    id: str = Field(description="bullet-id")
    tag: Literal["helpful", "harmful", "neutral"] = Field(
        description="tag classification"
    )


class Reflection(BaseModel):
    reasoning: str = Field(description="思考プロセスと詳細な分析および計算")
    error_identification: str = Field(
        description="推論において正確に何が間違っていたか"
    )
    root_cause_analysis: str = Field(
        description="このエラーが発生した理由は何か？どの概念が誤解されたか？"
    )
    correct_approach: str = Field(description="モデルは代わりに何をすべきだったか？")
    key_insight: str = Field(
        description="このようなエラーを避けるために記憶しておくべき戦略、公式、または原則は？"
    )
    bullet_tags: list[BulletTag] = Field(
        default_factory=list,
        description="bullet再タグ付け（idとhelpful/harmful/neutralタグ）",
    )

    @classmethod
    def from_dict(cls, payload: dict) -> "Reflection":
        return cls.model_validate(payload)


# ============================================
# リフレクター：エラー/パターンを批判的に分析
# ============================================
reflector_ = Agent(
    name="Reflector",
    model=config.reflector_model,
    description="ジェネレーターの結果を批判的に評価して教訓とデルタ候補を抽出する。",
    instruction="""
あなたのタスクは、ジェネレーターの産出物を入念に検討し、批判的に分析してリフレクション（JSON）を作成することです。

入力：
- ユーザークエリ: {user_query}
- ジェネレーター結果: {generator_output}
- ユーザーが期待した正答（ある場合）: {ground_truth}
- ジェネレーターが参照したプレイブックbullet: {app:playbook}

【必須分析ステップ】

1. モデルの推論軌跡を注意深く分析してエラーがどこで発生したかを把握してください
   - ジェネレーターのreasoning全体を確認してください
   - ロジック流で飛躍や矛盾がないか確認してください

2. 具体的なエラータイプを識別してください：概念エラー、計算間違い、戦略の誤用など
   - 各エラーの特性を明確に記述してください
   - 表面的なエラーの背後にある根本原因を見つけてください

3. モデルが今後同じ失敗をしないように実行可能な洞察を提供してください
   - 具体的な手順またはチェックリストを提示してください
   - 汎化可能な原則を導き出してください

4. ジェネレーターが使用した各bullet pointを評価してください
   - bullet_id別に['helpful', 'harmful', 'neutral']のいずれかをタグ付けしてください
   - helpful：正答に役立ったbullet
   - harmful：誤答に導いた誤ったまたは誤解させるbullet
   - neutral：最終結果に影響を与えなかったbullet

【出力ルール】
- reasoning：上記4つの分析ステップをすべて経た思考プロセス、詳細な分析と根拠
- error_identification：推論において正確に何が間違っていたかを具体的に記述
- root_cause_analysis：このエラーが発生した根本原因は？どの概念が誤解されたか？どの戦略が誤用されたか？
- correct_approach：ジェネレーターは代わりに何をすべきだったか？正確なステップとロジックを提示
- key_insight：このようなエラーを避けるために記憶しておくべき戦略、公式、原則、またはチェックリスト
- bullet_tags：ジェネレーターが参照した各bulletのタグ付け結果（idと'helpful'/'harmful'/'neutral'を含む）
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
            parts=[Part(text=f"[Reflector] Bulletのタグ付け結果:\n{pretty}")]
        )
        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            content=content,
            actions=EventActions(state_delta=state_changes),
        )


tag_bullet = TagBullet(name="tag_bullet", description="Bulletをタグ付けします。")

reflector = SequentialAgent(
    name="Reflector",
    description="ReflectorとTagBulletを順次実行します。",
    sub_agents=[reflector_, tag_bullet],
)
