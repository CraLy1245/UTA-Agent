from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from services.agent.usage_normalizer import NormalizedUsage
from services.api.app.db.models import (
    TokenAccount,
    TokenTransaction,
    Turn,
    TurnExecutionTrace,
)

UNITS_PER_TOKEN = 100
ACCOUNT_TYPES = ("read", "output")


@dataclass(frozen=True)
class LedgerEntry:
    transaction: TokenTransaction
    created: bool


def balances(db: Session) -> dict[str, TokenAccount]:
    accounts = {
        account.account_type: account
        for account in db.scalars(
            select(TokenAccount).where(TokenAccount.account_type.in_(ACCOUNT_TYPES))
        )
    }
    missing = [account_type for account_type in ACCOUNT_TYPES if account_type not in accounts]
    if missing:
        raise RuntimeError(f"Token accounts are missing: {', '.join(missing)}")
    return accounts


def balance_context(db: Session) -> str:
    accounts = balances(db)
    read = accounts["read"].balance_units
    output = accounts["output"].balance_units
    return (
        "Runtime survival balance (100 Units = 1 Token): "
        f"read={read} Units ({_format_tokens(read)} Tokens), "
        f"output={output} Units ({_format_tokens(output)} Tokens). "
        "These balances are informational: do not shorten necessary work, skip verification, "
        "or refuse the task solely because of the balance."
    )


def debit_completed_turn(
    db: Session,
    *,
    turn: Turn,
    model_id: str,
    normalized_usage: NormalizedUsage,
    raw_usages: list[dict[str, Any]],
    tool_names: list[str],
    tool_outcomes: list[dict[str, str]],
    memory_revision_ids: list[str],
    skill_revision_ids: list[str],
    latency_ms: int,
) -> tuple[TurnExecutionTrace, list[TokenTransaction]]:
    existing_trace = db.scalar(
        select(TurnExecutionTrace).where(TurnExecutionTrace.turn_id == turn.id)
    )
    if existing_trace is not None:
        transactions = list(
            db.scalars(
                select(TokenTransaction)
                .where(
                    TokenTransaction.turn_id == turn.id,
                    TokenTransaction.transaction_type == "usage_debit",
                )
                .order_by(TokenTransaction.account_type)
            )
        )
        return existing_trace, transactions

    usage_by_account = {
        "read": normalized_usage.input_tokens,
        "output": normalized_usage.output_tokens,
    }
    transactions: list[TokenTransaction] = []
    for account_type in ACCOUNT_TYPES:
        tokens = usage_by_account[account_type]
        entry = apply_transaction(
            db,
            turn_id=turn.id,
            feedback_event_id=None,
            account_type=account_type,
            transaction_type="usage_debit",
            amount_units=-(tokens * UNITS_PER_TOKEN),
            idempotency_key=f"debit:{turn.id}:{account_type}",
            metadata={
                "normalized_tokens": tokens,
                "usage_complete": normalized_usage.usage_complete,
            },
        )
        transactions.append(entry.transaction)

    objective_result = {
        "tool_call_count": len(tool_names),
        "tools": tool_outcomes,
    }
    trace = TurnExecutionTrace(
        id=str(uuid4()),
        turn_id=turn.id,
        model_id=model_id,
        memory_revision_ids_json=json.dumps(memory_revision_ids, ensure_ascii=False),
        skill_revision_ids_json=json.dumps(skill_revision_ids, ensure_ascii=False),
        tool_names_json=json.dumps(tool_names, ensure_ascii=False),
        provider_raw_usage_json=json.dumps(raw_usages, ensure_ascii=False),
        normalized_usage_json=json.dumps(normalized_usage.as_dict(), ensure_ascii=False),
        input_tokens=normalized_usage.input_tokens,
        output_tokens=normalized_usage.output_tokens,
        latency_ms=max(0, latency_ms),
        completion_status="completed",
        objective_result_json=json.dumps(objective_result, ensure_ascii=False),
    )
    db.add(trace)
    return trace, transactions


def apply_transaction(
    db: Session,
    *,
    turn_id: str,
    feedback_event_id: str | None,
    account_type: str,
    transaction_type: str,
    amount_units: int,
    idempotency_key: str,
    metadata: dict[str, Any],
) -> LedgerEntry:
    existing = db.scalar(
        select(TokenTransaction).where(TokenTransaction.idempotency_key == idempotency_key)
    )
    if existing is not None:
        return LedgerEntry(existing, False)
    balance_after = db.scalar(
        update(TokenAccount)
        .where(TokenAccount.account_type == account_type)
        .values(
            balance_units=TokenAccount.balance_units + amount_units,
            updated_at=datetime.now(UTC),
        )
        .returning(TokenAccount.balance_units)
    )
    if balance_after is None:
        raise RuntimeError(f"Token account is missing: {account_type}")
    transaction = TokenTransaction(
        id=str(uuid4()),
        turn_id=turn_id,
        feedback_event_id=feedback_event_id,
        account_type=account_type,
        transaction_type=transaction_type,
        amount_units=amount_units,
        balance_before=balance_after - amount_units,
        balance_after=balance_after,
        idempotency_key=idempotency_key,
        metadata_json=json.dumps(metadata, ensure_ascii=False),
        created_at=datetime.now(UTC),
    )
    db.add(transaction)
    return LedgerEntry(transaction, True)


def _format_tokens(units: int) -> str:
    whole, remainder = divmod(abs(units), UNITS_PER_TOKEN)
    sign = "-" if units < 0 else ""
    return f"{sign}{whole:,}.{remainder:02d}"
