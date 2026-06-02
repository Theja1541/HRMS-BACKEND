from django.contrib import admin
from .models import AssetCategory, Asset, AssetAssignment, AssetReturn, AssetMaintenance, AssetHistory

admin.site.register(AssetCategory)
admin.site.register(Asset)
admin.site.register(AssetAssignment)
admin.site.register(AssetReturn)
admin.site.register(AssetMaintenance)
admin.site.register(AssetHistory)
