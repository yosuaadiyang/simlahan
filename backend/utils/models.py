from django.db import models
from django.utils.translation import gettext_lazy as _


class RateCounter(models.Model):
    """Penghitung jatah per jendela waktu yang diperbarui atomik di basis data.

    Dipakai untuk kuota yang biayanya nyata (panggilan AI berbayar). Cache
    bawaan (DatabaseCache) tidak punya ``incr`` atomik, jadi permintaan
    serentak bisa melewati batas berbasis cache.
    """

    key = models.CharField(verbose_name=_("Key"), max_length=200, unique=True)
    count = models.PositiveIntegerField(verbose_name=_("Count"), default=0)
    expires_at = models.DateTimeField(verbose_name=_("Expires at"), db_index=True)

    class Meta:
        verbose_name = _("Rate counter")
        verbose_name_plural = _("Rate counters")

    def __str__(self):
        return f"{self.key}: {self.count}"
