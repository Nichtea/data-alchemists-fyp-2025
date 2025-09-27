road_max_traffic_flow_schema = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "road_id": {
                "type": "integer",
                "description": "Unique identifier for the road segment",
                "example": 1
            },
            "road_name": {
                "type": "string",
                "description": "Name of the road",
                "example": "ADAM ROAD"
            },
            "RoadCat": {
                "type": "string",
                "description": "Road category classification",
                "example": "CAT2"
            },
            "start_lat": {
                "type": "number",
                "description": "Latitude of the road start point",
                "example": 1.320198885
            },
            "start_lon": {
                "type": "number",
                "description": "Longitude of the road start point",
                "example": 103.8115894
            },
            "end_lat": {
                "type": "number",
                "description": "Latitude of the road end point",
                "example": 1.321445336
            },
            "end_lon": {
                "type": "number",
                "description": "Longitude of the road end point",
                "example": 103.8127463
            },
            "start_geom": {
                "type": "object",
                "description": "GeoJSON representation of the road start point",
                "properties": {
                    "type": {"type": "string", "example": "Point"},
                    "coordinates": {
                        "type": "array",
                        "items": {"type": "number"},
                        "example": [103.8115894, 1.320198885]
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
            },
            "end_geom": {
                "type": "object",
                "description": "GeoJSON representation of the road end point",
                "properties": {
                    "type": {"type": "string", "example": "Point"},
                    "coordinates": {
                        "type": "array",
                        "items": {"type": "number"},
                        "example": [103.8127463, 1.321445336]
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
            },
            "volume": {
                "type": "integer",
                "description": "Maximum observed traffic flow volume",
                "example": 850
            }
        },
        
    }
}



road_max_traffic_flow_by_id_schema = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "road_id": {"type": "integer", "description": "Unique identifier for the road segment", "example": 1},
            "road_name": {"type": "string", "description": "Name of the road", "example": "ADAM ROAD"},
            "RoadCat": {"type": "string", "description": "Road category classification", "example": "CAT2"},
            "start_lat": {"type": "number", "description": "Latitude of the road start point", "example": 1.320198885},
            "start_lon": {"type": "number", "description": "Longitude of the road start point", "example": 103.8115894},
            "end_lat": {"type": "number", "description": "Latitude of the road end point", "example": 1.321445336},
            "end_lon": {"type": "number", "description": "Longitude of the road end point", "example": 103.8127463},
            "start_geom": {
                "type": "object",
                "description": "GeoJSON of road start point",
                "properties": {
                    "type": {"type": "string", "example": "Point"},
                    "coordinates": {"type": "array", "items": {"type": "number"}, "example": [103.8115894, 1.320198885]},
                    "crs": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "example": "name"},
                            "properties": {"type": "object", "properties": {"name": {"type": "string", "example": "EPSG:4326"}}}
                        }
                    }
                }
            },
            "end_geom": {
                "type": "object",
                "description": "GeoJSON of road end point",
                "properties": {
                    "type": {"type": "string", "example": "Point"},
                    "coordinates": {"type": "array", "items": {"type": "number"}, "example": [103.8127463, 1.321445336]},
                    "crs": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "example": "name"},
                            "properties": {"type": "object", "properties": {"name": {"type": "string", "example": "EPSG:4326"}}}
                        }
                    }
                }
            },
            "volume": {"type": "integer", "description": "Maximum observed traffic flow volume", "example": 850}
        }
    }
}