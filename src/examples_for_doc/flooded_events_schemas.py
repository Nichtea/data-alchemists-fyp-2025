flood_events_schema = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "flood_id": {
                "type": "integer",
                "description": "Unique identifier of the flood event"
            },
            "flooded_location": {
                "type": "string",
                "description": "Location name where the flood occurred"
            },
            "date": {
                "type": "string",
                "format": "date",
                "description": "Date of the flood event"
            },
            "daily rainfall total (mm)": {
                "type": "number",
                "description": "Total daily rainfall (in mm)"
            },
            "highest 30 min rainfall (mm)": {
                "type": "number",
                "description": "Maximum rainfall within 30 minutes (in mm)"
            },
            "highest 60 min rainfall (mm)": {
                "type": "number",
                "description": "Maximum rainfall within 60 minutes (in mm)"
            },
            "highest 120 min rainfall (mm)": {
                "type": "number",
                "description": "Maximum rainfall within 120 minutes (in mm)"
            },
            "mean_pr": {
                "type": "number",
                "description": "Mean precipitation rate"
            },
            "latitude": {
                "type": "number",
                "format": "float",
                "description": "Latitude of the flood location"
            },
            "longitude": {
                "type": "number",
                "format": "float",
                "description": "Longitude of the flood location"
            },
            "geom": {
                "type": "object",
                "description": "GeoJSON geometry of the flood event",
                "properties": {
                    "type": {"type": "string", "example": "Point"},
                    "coordinates": {
                        "type": "array",
                        "items": {"type": "number"},
                        "example": [103.8349951, 1.429525229]
                    },
                    "crs": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "example": "name"},
                            "properties": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string", "example": "EPSG:4326"}
                                }
                            }
                        }
                    }
                }
            }
        },
        "required": ["flood_id", "flooded_location", "date", "latitude", "longitude"]
    }
}



flood_event_by_id_schema = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "flood_id": {
                "type": "integer",
                "description": "Unique identifier of the flood event"
            },
            "road_name": {
                "type": "string",
                "description": "Name of the nearest road affected by the flood"
            },
            "road_type": {
                "type": "string",
                "description": "Type of road (e.g., primary, residential)"
            },
            "length_m": {
                "type": "number",
                "format": "float",
                "description": "Length of affected road segment in meters"
            },
            "geometry": {
                "type": "string",
                "description": "WKT LINESTRING representing the road geometry"
            }
        }
    }
}