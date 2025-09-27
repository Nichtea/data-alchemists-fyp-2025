get_all_flood_events_example = [
    {
        "flood_id": 1,
        "flooded_location": "Yishun MRT",
        "date": "2014-03-20",
        "daily rainfall total (mm)": 45,
        "highest 30 min rainfall (mm)": 40.8,
        "highest 60 min rainfall (mm)": 44,
        "highest 120 min rainfall (mm)": 44.2,
        "mean_pr": 17.3950819672131,
        "latitude": 1.429525229,
        "longitude": 103.8349951,
        "geom": {
            "type": "Point",
            "coordinates": [103.8349951, 1.429525229],
            "crs": {
                "type": "name",
                "properties": {"name": "EPSG:4326"}
            }
        }
    },
    {
        "flood_id": 2,
        "flooded_location": "2 KAKI BUKIT ROAD 3",
        "date": "2014-04-04",
        "daily rainfall total (mm)": 25,
        "highest 30 min rainfall (mm)": 21,
        "highest 60 min rainfall (mm)": 25,
        "highest 120 min rainfall (mm)": 25,
        "mean_pr": 7.99354838709677,
        "latitude": 1.337333619,
        "longitude": 103.9019432,
        "geom": {
            "type": "Point",
            "coordinates": [103.9019432, 1.337333619],
            "crs": {
                "type": "name",
                "properties": {"name": "EPSG:4326"}
            }
        }
    }
]


flood_event_by_id_example = [
    {
        "flood_id": 1,
        "road_name": "Yishun Avenue 2",
        "road_type": "primary",
        "length_m": 616.4873388504224,
        "geometry": "LINESTRING (103.8350704 1.4248212, 103.8350717 1.4248739, 103.8351006 1.4260113, ...)"
    },
    {
        "flood_id": 12,
        "road_name": "MacKenzie Road",
        "road_type": "residential",
        "length_m": 257.5635671396551,
        "geometry": "LINESTRING (103.8484492 1.3055518, 103.8483005 1.3056599, 103.8481111 1.3057976, ...)"
    }
]