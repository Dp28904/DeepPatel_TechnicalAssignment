"""Hosting settings: TLS to a hosted MySQL is opt-in, via a file path or the certificate text."""

import pathlib

import pytest
from pydantic import ValidationError

from app.core import database
from app.core.config import Settings

PEM = "-----BEGIN CERTIFICATE-----\nMIIBfakecertificatebody\n-----END CERTIFICATE-----"


def settings(**overrides) -> Settings:
    return Settings(database_url="mysql+pymysql://x", secret_key="k" * 16, **overrides)


def use(monkeypatch, value: Settings) -> None:
    monkeypatch.setattr(database, "get_settings", lambda: value)


def test_no_tls_options_by_default(monkeypatch):
    use(monkeypatch, settings())
    assert database.connect_args() == {}


def test_tls_with_a_certificate_file(monkeypatch, tmp_path):
    ca = tmp_path / "ca.pem"
    ca.write_text(PEM)
    use(monkeypatch, settings(database_ssl_ca=str(ca)))
    assert database.connect_args() == {"ssl": {"ca": str(ca)}}


def test_missing_certificate_file_gives_a_clear_message():
    with pytest.raises(ValidationError) as error:
        settings(database_ssl_ca="/etc/secrets/ca.pem")
    message = str(error.value)
    assert "no file exists there" in message and "Secret Files" in message


def test_tls_with_certificate_text_in_an_environment_variable(monkeypatch):
    use(monkeypatch, settings(database_ssl_ca_pem=PEM))
    ca_path = database.connect_args()["ssl"]["ca"]
    assert pathlib.Path(ca_path).read_text().strip() == PEM


def test_certificate_text_pasted_on_one_line_is_accepted(monkeypatch):
    use(monkeypatch, settings(database_ssl_ca_pem=PEM.replace("\n", "\\n")))
    ca_path = database.connect_args()["ssl"]["ca"]
    assert pathlib.Path(ca_path).read_text().strip() == PEM


def test_certificate_text_wins_over_a_missing_file_path(monkeypatch):
    use(monkeypatch, settings(database_ssl_ca="/does/not/exist.pem", database_ssl_ca_pem=PEM))
    assert pathlib.Path(database.connect_args()["ssl"]["ca"]).is_file()


def test_certificate_text_must_look_like_a_certificate():
    with pytest.raises(ValidationError, match="BEGIN CERTIFICATE"):
        settings(database_ssl_ca_pem="not a certificate")


def test_production_mode_is_read_from_app_env():
    assert settings(app_env="production").is_production
    assert not settings(app_env="development").is_production


# --- Hosted-provider URLs (e.g. Aiven's "Service URI") -------------------------------------
@pytest.mark.parametrize(
    ("given", "expected_url", "expected_mode"),
    [
        (
            "mysql://avnadmin:pw@host.aivencloud.com:12345/defaultdb?ssl-mode=REQUIRED",
            "mysql+pymysql://avnadmin:pw@host.aivencloud.com:12345/defaultdb",
            "REQUIRED",
        ),
        ("mysql+pymysql://u:p@h:3306/db", "mysql+pymysql://u:p@h:3306/db", None),
        (
            "mysql+mysqldb://u:p@h/db?charset=utf8mb4&ssl_mode=required",
            "mysql+pymysql://u:p@h/db?charset=utf8mb4",
            "REQUIRED",
        ),
        ("  mysql://u:p%40ss@h/db  ", "mysql+pymysql://u:p%40ss@h/db", None),
    ],
)
def test_provider_urls_are_normalised(given, expected_url, expected_mode):
    s = Settings(database_url=given, secret_key="k" * 16)
    assert s.database_url == expected_url
    assert s.database_ssl_mode == expected_mode


def test_ssl_mode_required_without_ca_encrypts_without_verification(monkeypatch):
    use(monkeypatch, settings(database_ssl_mode="required"))
    assert database.connect_args() == {"ssl": {"verify_mode": False}}


def test_a_ca_certificate_always_gives_full_verification(monkeypatch, tmp_path):
    ca = tmp_path / "ca.pem"
    ca.write_text(PEM)
    use(monkeypatch, settings(database_ssl_mode="REQUIRED", database_ssl_ca=str(ca)))
    assert database.connect_args() == {"ssl": {"ca": str(ca)}}


def test_ssl_mode_disabled_means_no_tls(monkeypatch):
    use(monkeypatch, settings(database_ssl_mode="DISABLED"))
    assert database.connect_args() == {}


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"database_ssl_mode": "SOMETIMES"}, "is not valid"),
        ({"database_ssl_mode": "VERIFY_CA"}, "needs the database's CA certificate"),
    ],
)
def test_bad_ssl_settings_explain_themselves(overrides, message):
    with pytest.raises(ValidationError, match=message):
        settings(**overrides)


def test_certificate_pasted_into_the_path_variable_is_recognised(monkeypatch):
    """The slip seen on Render: certificate text in DATABASE_SSL_CA instead of _PEM."""
    s = settings(database_ssl_ca=PEM.replace("\n", "\\n"))
    assert s.database_ssl_ca is None and "BEGIN CERTIFICATE" in s.database_ssl_ca_pem
    use(monkeypatch, s)
    assert pathlib.Path(database.connect_args()["ssl"]["ca"]).read_text().strip() == PEM


def test_an_impossible_path_gives_the_clear_message_not_a_crash():
    with pytest.raises(ValidationError, match="no file exists there"):
        settings(database_ssl_ca="x" * 5000)
