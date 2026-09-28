"""
Kite chain configuration for the x402 Python/FastAPI wrapper template.

Mirrors the TypeScript and Go templates' kite.ts / kite.go — defines the two
Kite networks (mainnet / testnet) that the wrapper can charge on, and a
custom money parser that converts "$0.001"-style prices into the correct
EIP-3009 transferWithAuthorization domain for the Kite facilitator.

Files that import this module:
    server.py — FastAPI application entry point
"""

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

# ---------------------------------------------------------------------------
# Kite chain descriptor
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class KiteChain:
    """One Kite network the wrapper can charge on.

    Only the stablecoin that the Kite facilitator settles for that network is
    listed: the payer signs an EIP-3009 transferWithAuthorization, so the
    asset must implement EIP-3009 and the EIP-712 domain (name/version) must
    match the token contract exactly or the facilitator rejects the signature.
    """

    network: str                     # CAIP-2 identifier
    rpc_url: str
    asset_address: str               # stablecoin contract
    asset_symbol: str
    asset_decimals: int
    eip712_name: str
    eip712_version: str

    # The facilitator that verifies and settles on this network.
    facilitator_url: str = "https://facilitator.pieverse.io/v2"

    @property
    def chain_id(self) -> int:
        """Extract EVM chain ID from the CAIP-2 network identifier."""
        return int(self.network.split(":")[-1])


# ---- Kite mainnet: Bridged USDC (USDC.e), 6 decimals ----
KITE_MAINNET = KiteChain(
    network="eip155:2366",
    rpc_url="https://rpc.gokite.ai",
    asset_address="0x7aB6f3ed87C42eF0aDb67Ed95090f8bF5240149e",
    asset_symbol="USDC.e",
    asset_decimals=6,
    eip712_name="Bridged USDC (Kite AI)",
    eip712_version="2",
)

# ---- Kite testnet: pieUSD, 18 decimals ----
# Kite Passport sandbox agents pay with this.
KITE_TESTNET = KiteChain(
    network="eip155:2368",
    rpc_url="https://rpc-testnet.gokite.ai",
    asset_address="0x38129cf4CE5E183eFF248F42A7D345Bb1B47621A",
    asset_symbol="pieUSD",
    asset_decimals=18,
    eip712_name="pieUSD",
    eip712_version="1",
)

# Default facilitator (used when FACILITATOR_URL env var is unset).
FACILITATOR_URL = "https://facilitator.pieverse.io/v2"

# Map string name -> KiteChain
_CHAINS: dict[str, KiteChain] = {
    "mainnet": KITE_MAINNET,
    "testnet": KITE_TESTNET,
}


def kite_chain_by_name(name: str | None) -> KiteChain:
    """Resolve the KITE_NETWORK environment value (``mainnet`` or ``testnet``).

    Raises ValueError on unknown names.
    """
    key = (name or "mainnet").strip().lower()
    if key in ("", "mainnet"):
        return KITE_MAINNET
    if key == "testnet":
        return KITE_TESTNET
    raise ValueError(f'unknown KITE_NETWORK "{name}" (want mainnet or testnet)')


def kite_money_parser(chain: KiteChain):
    """Return a ``MoneyParser`` that handles ``$0.001``-style prices on the
    given Kite chain.

    The returned callable conforms to :class:`ExactEvmServerScheme`'s
    ``register_money_parser`` signature:

        (decimal_amount: str | int | float, network: str) -> AssetAmount | None

    It returns ``None`` for networks that are not this chain, so multiple
    parsers can be chained.
    """
    from x402.schemas import AssetAmount

    def parser(amount: str | int | float, network: str) -> AssetAmount | None:
        if network != chain.network:
            return None  # not ours; let the next parser try

        # Normalise to a decimal string (strip leading "$" if present).
        text = str(amount).strip()
        if text.startswith("$"):
            text = text[1:]

        try:
            value = Decimal(text)
        except InvalidOperation:
            raise ValueError(f"price must be a positive decimal, got {amount}")

        if value <= 0:
            raise ValueError(f"price must be positive, got {amount}")

        # Convert to atomic units (smallest denomination).
        factor = Decimal(10) ** chain.asset_decimals
        units = int(value * factor)
        if units <= 0:
            raise ValueError(
                f"price {amount} is below one unit of {chain.asset_symbol}"
            )

        return AssetAmount(
            amount=str(units),
            asset=chain.asset_address,
            extra={
                "name": chain.eip712_name,
                "version": chain.eip712_version,
            } if chain.eip712_name else None,
        )

    return parser
