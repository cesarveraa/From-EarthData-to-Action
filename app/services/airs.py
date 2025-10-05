from ..schemas.common import DataSource

def airs_urls(date_iso: str | None):
    collection = "AIRS3STD.006"
    base = "https://acdisc.gesdisc.eosdis.nasa.gov/opendap/Aqua_AIRS_Level3"
    return [
        DataSource(
            name="AIRS L3 Daily (OPeNDAP)",
            url=f"{base}/{collection}/<YYYY>/<AIRS*.hdf>",
            note="Temperatura/humedad diaria; Earthdata requerido.",
            auth_required=True
        )
    ]
