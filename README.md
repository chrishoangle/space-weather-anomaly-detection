# Space Weather Anomaly Detection

Detect anomalous events in NOAA solar wind and geomagnetic time series data 
using unsupervised and semi-supervised methods.

## Motivation

Space weather events (coronal mass ejections, solar flares, high-speed streams) 
can damage satellites, disrupt GPS, and affect power grids. Reliable early detection 
of anomalous solar wind behavior enables mitigation.

## Approach

1. Ingest historical solar wind and geomagnetic data from NOAA SWPC / NASA OMNIWeb
2. Establish baseline behavior via statistical characterization  
3. Apply anomaly detection methods (statistical process control, Isolation Forest, 
   autoencoder) to identify deviations
4. Validate detected anomalies against known geomagnetic storm events
5. Deploy an interactive dashboard for real-time monitoring

## Tech Stack

- Python (pandas, NumPy, scikit-learn)
- Streamlit for dashboard
- Deployment: Streamlit Community Cloud

## Data Sources

- NOAA SWPC real-time and historical products
- NASA OMNIWeb historical archive
- Known storm event catalog for validation

## Status

In development.
