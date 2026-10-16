from django.core import validators as core_validators
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _

# NPWP (Nomor Pokok Wajib Pajak) badan usaha: 15 digit (format lama
# 99.999.999.9-999.999) atau 16 digit (format baru sejak 2024, sama dengan NIK
# untuk orang pribadi). Tanda baca titik/strip diperbolehkan.
business_id_re = core_validators._lazy_re_compile(
    r"^(?:\d{15}|\d{16}|\d{2}\.\d{3}\.\d{3}\.\d-\d{3}\.\d{3})$"
)
validate_business_id = core_validators.RegexValidator(
    business_id_re, _("Enter a valid business id."), "invalid"
)

# NIK (Nomor Induk Kependudukan): 16 digit.
national_identification_number_re = core_validators._lazy_re_compile(r"^\d{16}$")
validate_national_identification_number = core_validators.RegexValidator(
    national_identification_number_re,
    _("Enter a valid national identification number (16 digits)."),
    "invalid",
)


class HexColorValidator(RegexValidator):
    # Startswith `#`, then has either 1 or 2 groups of 3 characters
    # that are 0-9 or a-f or A-F
    regex = r"^#(?:[0-9a-fA-F]{3}){1,2}$"
    message = "Enter a valid hex color code, e.g. #000000 or #FFF"
