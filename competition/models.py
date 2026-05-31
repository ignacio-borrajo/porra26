from django.db import models


class Team(models.Model):
    code = models.CharField(primary_key=True, max_length=3)
    name = models.CharField(max_length=80)
    flag = models.CharField(max_length=8)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
