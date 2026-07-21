from verification.submission_atomicity.modelo_estados import explorar


def test_modelo_acotado_preserva_invariantes() -> None:
    resultado = explorar()
    assert resultado["ok"] is True
    assert resultado["estados_explorados"] > 10
    assert resultado["estados_finales"] > 0
