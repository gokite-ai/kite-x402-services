"""Tests for kite.py — Kite chain configuration and money parser."""
import sys

sys.path.insert(0, ".")

from kite import KITE_MAINNET, KITE_TESTNET, kite_chain_by_name, kite_money_parser
from x402.schemas import AssetAmount


class TestKiteConfig:
    def test_mainnet_chain_id(self):
        assert KITE_MAINNET.chain_id == 2366

    def test_testnet_chain_id(self):
        assert KITE_TESTNET.chain_id == 2368

    def test_asset_decimals(self):
        assert KITE_TESTNET.asset_decimals == 18

    def test_kite_network_default(self):
        chain = kite_chain_by_name("testnet")
        assert chain.network == "eip155:2368"
        assert chain.asset_symbol == "pieUSD"

    def test_kite_network_mainnet(self):
        chain = kite_chain_by_name("mainnet")
        assert chain.network == "eip155:2366"
        assert chain.asset_symbol == "USDC.e"

    def test_kite_network_invalid(self):
        import pytest

        with pytest.raises(ValueError, match="unknown KITE_NETWORK"):
            kite_chain_by_name("invalid")


class TestMoneyParser:
    def setup_method(self):
        self.chain = kite_chain_by_name("testnet")
        self.parse = kite_money_parser(self.chain)

    def test_returns_asset_amount(self):
        result = self.parse(0.001, self.chain.network)
        assert isinstance(result, AssetAmount)

    def test_dollar_prefix(self):
        result = self.parse("$0.001", self.chain.network)
        assert isinstance(result, AssetAmount)
        assert int(result.amount) > 0

    def test_none_for_wrong_network(self):
        result = self.parse(0.001, "eip155:1")
        assert result is None

    def test_zero_rejected(self):
        import pytest

        with pytest.raises(ValueError, match="price must be positive"):
            self.parse(0, self.chain.network)

    def test_negative_rejected(self):
        import pytest

        with pytest.raises(ValueError, match="price must be positive"):
            self.parse(-1, self.chain.network)

    def test_atomic_units(self):
        result = self.parse(0.001, self.chain.network)
        assert int(result.amount) == 10**15

    def test_asset_address(self):
        result = self.parse(0.001, self.chain.network)
        assert result.asset == KITE_TESTNET.asset_address

    def test_kite_asset_config_testnet(self):
        cfg = kite_chain_by_name("testnet")
        assert cfg.asset_symbol == "pieUSD"
        assert cfg.asset_decimals == 18
