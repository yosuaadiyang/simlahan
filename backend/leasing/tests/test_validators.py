import pytest
from django.core.exceptions import ValidationError

from leasing import validators
from leasing.models.map_layers import HexColorValidator


def test_business_id_validator():
    # NPWP 15 digit (format lama), dengan dan tanpa tanda baca
    validators.validate_business_id("012345678901000")
    validators.validate_business_id("01.234.567.8-901.000")
    # NPWP 16 digit (format baru)
    validators.validate_business_id("0012345678901000")

    with pytest.raises(ValidationError):
        validators.validate_business_id("1234567-8")

    with pytest.raises(ValidationError):
        validators.validate_business_id("01234567890100")


def test_national_identification_number_validator():
    validators.validate_national_identification_number("2171011501900001")

    with pytest.raises(ValidationError):
        validators.validate_national_identification_number("010190-123A")

    with pytest.raises(ValidationError):
        validators.validate_national_identification_number("217101150190000")


@pytest.fixture
def validator():
    return HexColorValidator()


@pytest.mark.parametrize(
    "hex_color",
    [
        "#FFFFFF",
        "#000000",
        "#FFF",
        "#000",
        "#1F2A3B",
    ],
)
def test_valid_hex_color(validator, hex_color):
    try:
        validator(hex_color)
    except ValidationError:
        pytest.fail("ValidationError was raised")


@pytest.mark.parametrize(
    "hex_color",
    [
        "FFFFFF",
        "123",
        "#00",
        "#FF00",
        "#GGG",
        "#1A2B3Z",
    ],
)
def test_invalid_hex_color(validator, hex_color):
    with pytest.raises(ValidationError):
        validator(hex_color)
