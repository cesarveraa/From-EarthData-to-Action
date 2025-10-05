# AirHealth Data API (FastAPI) — Solo datos (NASA/OpenAQ/AirNow)

## Instalar
python -m venv .venv
# Activar venv...
pip install -r App/requirements.txt
cp App/.env.example App/.env  # Completa credenciales si las tienes

## Ejecutar
uvicorn App.main:app --reload --host 0.0.0.0 --port 8000

## Probar
# Calidad de aire (La Paz) con aerosoles MODIS
curl -X POST http://localhost:8000/data/air_quality \
 -H "Content-Type: application/json" \
 -d '{"location":{"lat":-16.5,"lon":-68.15},"when":"2025-10-05T13:00:00Z","radius_km":20,"include_ground":true,"include_sat":true,"gibs_layer":"MODIS_Terra_Aerosol"}'

# Precipitación (IMERG 24h atrás/adelante)
curl -X POST http://localhost:8000/data/precipitation \
 -H "Content-Type: application/json" \
 -d '{"location":{"lat":-16.5,"lon":-68.15},"when":"2025-10-05T13:00:00Z","hours_back":24,"hours_fwd":24}'

# Temperatura (AIRS + MERRA-2 + nubes GIBS)
curl -X POST http://localhost:8000/data/temperature \
 -H "Content-Type: application/json" \
 -d '{"location":{"lat":-16.5,"lon":-68.15},"when":"2025-10-05T13:00:00Z"}'

# Viento (MERRA-2 + referencias CYGNSS/AMSR2)
curl -X POST http://localhost:8000/data/wind \
 -H "Content-Type: application/json" \
 -d '{"location":{"lat":-16.5,"lon":-68.15},"when":"2025-10-05T13:00:00Z"}'
# From-EarthData-to-Action
