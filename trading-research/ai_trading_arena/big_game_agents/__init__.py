from __future__ import annotations

from .benchmarks import human_60_40, human_qqq_buy_hold, human_spy_buy_hold
from .options_agents import (
    options_committee_veto,
    options_human_overseer,
    options_no_intervention,
    options_risk_rules,
)
from .stock_agents import anything_cross_asset, normal_sector_stock


def build_big_game_agents():
    return {
        "Human_SPY_BuyHold": human_spy_buy_hold,
        "Human_QQQ_BuyHold": human_qqq_buy_hold,
        "Human_60_40": human_60_40,
        "Normal_SectorStockAgent": normal_sector_stock,
        "OptionsOnly_NoIntervention": options_no_intervention,
        "Options_RiskRules": options_risk_rules,
        "Options_HumanOverseer": options_human_overseer,
        "Options_CommitteeVeto": options_committee_veto,
        "Anything_CrossAssetAgent": anything_cross_asset,
    }
