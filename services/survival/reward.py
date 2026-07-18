from __future__ import annotations

from sqlalchemy.orm import Session

from services.api.app.db.models import FeedbackEvent, TurnExecutionTrace
from services.survival.ledger import ACCOUNT_TYPES, LedgerEntry, apply_transaction


def grant_survival_reward(
    db: Session, *, feedback_event: FeedbackEvent, trace: TurnExecutionTrace
) -> list[LedgerEntry]:
    tokens_by_account = {"read": trace.input_tokens, "output": trace.output_tokens}
    rewards: list[LedgerEntry] = []
    for account_type in ACCOUNT_TYPES:
        tokens = tokens_by_account[account_type]
        rewards.append(
            apply_transaction(
                db,
                turn_id=trace.turn_id,
                feedback_event_id=feedback_event.id,
                account_type=account_type,
                transaction_type="survival_reward",
                amount_units=tokens * 108,
                idempotency_key=f"reward:{trace.turn_id}:{account_type}",
                metadata={
                    "feedback_event_id": feedback_event.id,
                    "reward_percent": 108,
                    "normalized_tokens": tokens,
                },
            )
        )
    return rewards


def reward_was_granted(entries: list[LedgerEntry]) -> bool:
    return any(entry.created for entry in entries)
