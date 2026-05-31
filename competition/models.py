from django.db import models


class Team(models.Model):
    code = models.CharField(primary_key=True, max_length=3)
    name = models.CharField(max_length=80)
    flag = models.CharField(max_length=8)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Round(models.Model):
    id = models.CharField(primary_key=True, max_length=10)
    label = models.CharField(max_length=40)
    short = models.CharField(max_length=10)
    points = models.PositiveSmallIntegerField()
    order = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.label
