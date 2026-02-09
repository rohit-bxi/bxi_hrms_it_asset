# -*- coding: utf-8 -*-
from collections import defaultdict
from functools import lru_cache
import re

from odoo import models

try:
    import qrcode
    import qrcode.image.svg
except Exception:  # pragma: no cover
    qrcode = None


@lru_cache(maxsize=2048)
def _qr_svg(value: str) -> str:
    """Return an inline SVG (string) for a QR code.

    Vector SVG is embedded directly into the report HTML so it does not require
    ReportLab renderPM (PNG backend).
    """
    value = (value or "").strip()
    if not value or qrcode is None:
        return ""

    factory = qrcode.image.svg.SvgImage
    img = qrcode.make(value, image_factory=factory, border=1)
    svg = img.to_string().decode("utf-8", errors="ignore")

    # Remove XML header if present
    svg = svg.replace("<?xml version='1.0' encoding='UTF-8'?>", "")
    svg = svg.replace('<?xml version="1.0" encoding="UTF-8"?>', "")

    # Make it responsive inside the container (outer div controls final size)
    svg = re.sub(r'\swidth="[^"]+"', ' width="100%"', svg)
    svg = re.sub(r'\sheight="[^"]+"', ' height="100%"', svg)
    return svg


def _prepare_data(env, docids, data):
    """Prepare data for asset label reports - Odoo 18 version"""
    layout_wizard = env['asset.label.layout'].browse(data.get('layout_wizard'))
    Asset = env['asset.management']
    
    if not layout_wizard:
        return {}

    total = 0
    qty_by_asset_in = data.get('quantity_by_asset')
    # Search for assets all at once, ordered by name desc
    assets = Asset.search([('id', 'in', [int(a) for a in qty_by_asset_in.keys()])], order='name desc')
    quantity_by_asset = defaultdict(list)
    
    for asset in assets:
        q = qty_by_asset_in[str(asset.id)]
        # Use barcode if available, otherwise use asset name as barcode
        barcode_value = asset.barcode if asset.barcode else asset.name
        quantity_by_asset[asset].append((barcode_value, q))
        total += q

    # Get custom dimensions if provided
    custom_columns = data.get('custom_columns')
    custom_rows = data.get('custom_rows')
    
    # Use custom dimensions if provided, otherwise use wizard dimensions
    columns = custom_columns if custom_columns else layout_wizard.columns
    rows = custom_rows if custom_rows else layout_wizard.rows
    
    # Get red band color from data, default to #dc3545
    red_band_color = data.get('red_band_color', '#dc3545')

    # Precompute QR SVGs for all barcodes so QWeb doesn't need to call Python functions
    qr_svg_map = {}
    try:
        for _asset, _items in quantity_by_asset.items():
            for _bc, _q in _items:
                _bc = (_bc or "").strip()
                if _bc and _bc not in qr_svg_map:
                    qr_svg_map[_bc] = _qr_svg(_bc)
    except Exception:
        qr_svg_map = {}

return {
        'quantity': quantity_by_asset,
        'page_numbers': (total - 1) // (rows * columns) + 1 if (rows * columns) > 0 else 1,
        'price_included': data.get('price_included'),
        'columns': columns,
        'rows': rows,
        'red_band_color': red_band_color,
        'qr_svg_map': qr_svg_map,
    }


class ReportAssetTemplateLabel2x7(models.AbstractModel):
    _name = 'report.asset_management.report_assettemplatelabel2x7'
    _description = 'Asset Label Report 2x7'

    def _get_report_values(self, docids, data):
        return _prepare_data(self.env, docids, data)


class ReportAssetTemplateLabel4x7(models.AbstractModel):
    _name = 'report.asset_management.report_assettemplatelabel4x7'
    _description = 'Asset Label Report 4x7'

    def _get_report_values(self, docids, data):
        return _prepare_data(self.env, docids, data)


class ReportAssetTemplateLabel4x12(models.AbstractModel):
    _name = 'report.asset_management.report_assettemplatelabel4x12'
    _description = 'Asset Label Report 4x12'

    def _get_report_values(self, docids, data):
        return _prepare_data(self.env, docids, data)


class ReportAssetTemplateLabel4x12NoPrice(models.AbstractModel):
    _name = 'report.asset_management.report_assettemplatelabel4x12noprice'
    _description = 'Asset Label Report 4x12 No Price'

    def _get_report_values(self, docids, data):
        return _prepare_data(self.env, docids, data)


class ReportAssetTemplateLabelDymo(models.AbstractModel):
    _name = 'report.asset_management.report_assettemplatelabel_dymo'
    _description = 'Asset Label Report Dymo'

    def _get_report_values(self, docids, data):
        return _prepare_data(self.env, docids, data)


class ReportAssetTemplateLabelCustom(models.AbstractModel):
    _name = 'report.asset_management.report_assettemplatelabel_custom'
    _description = 'Asset Label Report Custom Columns'

    def _get_report_values(self, docids, data):
        return _prepare_data(self.env, docids, data)

