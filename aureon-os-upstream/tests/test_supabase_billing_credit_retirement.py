"""Unverified browser claims must never create or disclose billing credit."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_topup_function_is_a_fixed_no_mutation_response() -> None:
    source = _source("supabase/functions/gas-tank-topup/index.ts")

    assert "UNVERIFIED_BALANCE_CREDIT_DISABLED" in source
    assert "provider_verified_payment_webhook" in source
    assert "balanceMutationAttempted: false" in source
    assert "providerReceiptVerified: false" in source
    assert "status: 503" in source
    for forbidden in (
        "Deno.env.get", "createClient", "SUPABASE_SERVICE_ROLE_KEY",
        "await req.json", ".insert(", ".update(", ".upsert(",
    ):
        assert forbidden not in source


def test_balance_function_cannot_disclose_an_arbitrary_users_account() -> None:
    source = _source("supabase/functions/gas-tank-check-balance/index.ts")

    assert "PRIVILEGED_BALANCE_LOOKUP_DISABLED" in source
    assert "authenticated_rls_account_read" in source
    assert "balanceDisclosed: false" in source
    assert "serviceRoleUsed: false" in source
    assert "status: 503" in source
    for forbidden in (
        "Deno.env.get", "createClient", "SUPABASE_SERVICE_ROLE_KEY",
        "await req.json", ".from(", ".select(",
    ):
        assert forbidden not in source


def test_frontend_has_no_self_confirmed_credit_path() -> None:
    support = _source("frontend/src/components/SupportProjectPrompt.tsx")
    gas_tank = _source("frontend/src/hooks/useGasTank.ts")

    assert "gas-tank-topup" not in support
    assert "gas-tank-topup" not in gas_tank
    assert "self_confirmed" not in support
    assert "payment_transactions" not in support
    assert "PROVIDER_VERIFIED_TOPUP_REQUIRED" in gas_tank
