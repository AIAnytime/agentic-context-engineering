from google.adk.agents import Agent
from pydantic import BaseModel, Field

from config import Config

config = Config()


# -------------------------
# 1) ジェネレーター出力スキーマ
# -------------------------
class GeneratorOutput(BaseModel):
    reasoning: list[str] = Field(
        description="[段階別の思考プロセス / 推論プロセス / 詳細な分析と計算] の形式で段階別推論プロセスを提供する"
    )
    bullet_ids: list[str] = Field(
        default_factory=list, description="参照したプレイブックのbullet IDリスト"
    )
    final_answer: str = Field(description="簡潔な最終答")


# ============================================
# ジェネレーター：プレイブックを利用して答と軌跡を生成
# ============================================
generator = Agent(
    name="Generator",
    model=config.generator_model,
    description="プレイブックを参考に問題を解決し、最終答を構造化して返す。",
    instruction="""
あなたのタスクは、ユーザークエリに答えながら、段階別推論と使用したbullet IDを構造化して提供することです。

入力：
- ユーザークエリ: {user_query}
- 現在のPlaybook: {app:playbook}

【必須ガイドライン】

1. プレイブックを注意深く読み、関連する戦略、公式、洞察を適用してください
   - プレイブックのすべてのbullet pointを確認してください
   - 各戦略の文脈と適用条件を理解してください

2. プレイブックにリストされた一般的な失敗（アンチパターン）を注意深く調べ、回避してください
   - 具体的な代替案またはベストプラクティスを提示してください

3. 段階的に推論プロセスを示してください
   - 各段階でどのbulletを参照したかを明示してください
   - ロジックの流れが明確になるように構成してください

4. 分析は徹底的だが簡潔に作成してください
   - 必須情報のみを含め、中心的な根拠はすべて含めてください
   - 不要な繰り返しを避けてください

5. 最終答を提供する前に、計算とロジックを再検討してください
   - すべての参照bullet_idが実際に使用されたことを確認してください
   - ロジック上の矛盾がないか確認してください
   - プレイブックbulletのうち関連があるものを見落としていないか再確認してください

【出力ルール】
- reasoning: 段階別の思考プロセス（step-by-step chain of thought）、詳細な分析と計算
- bullet_ids: 参照したplaybook bullet IDのリスト
- final_answer: 明確で検証された最終答
""",
    include_contents="none",  # 状態値の注入中心
    output_schema=GeneratorOutput,  # 出力を構造化
    output_key="generator_output",  # session.state['generator_output']に保存
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
)
