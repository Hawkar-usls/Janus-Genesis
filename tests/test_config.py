from janus_genesis.config import JanusConfig


def test_default_config_is_bambu_a1_pla() -> None:
    config = JanusConfig()
    assert config.printer.name == "Bambu Lab A1"
    assert config.printer.nozzle_mm == 0.4
    assert config.material.name == "Generic PLA"
    assert config.material.calibrated is False
