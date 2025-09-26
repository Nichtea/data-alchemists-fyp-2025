bus_stops_schema = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "stop_id": {"type": "string", "description": "Unique identifier of the bus stop"},
            "stop_code": {"type": "string", "description": "Official bus stop code"},
            "stop_name": {"type": "string", "description": "Name of the bus stop"},
            "stop_lat": {"type": "number", "format": "float", "description": "Latitude"},
            "stop_lon": {"type": "number", "format": "float", "description": "Longitude"},
            "wheelchair_boarding": {"type": "string", "description": "1 if wheelchair accessible, 0 if not"},
            "geom": {"type": "string", "nullable": True, "description": "Geometry data for mapping"},
            "stop_desc": {"type": "string", "nullable": True, "description": "Optional description"},
            "stop_url": {"type": "string", "nullable": True, "description": "Optional URL for more info"}
        },
        "required": ["stop_id"]
    }
}


bus_trip_schema = {
    "type": "object",
    "properties": {
        "bus_trip_id": {"type": "integer", "description": "Bus trip ID"},
        "start_area_code": {"type": "string", "description": "Start area code"},
        "start_lat": {"type": "number", "format": "float", "description": "Start latitude"},
        "start_lon": {"type": "number", "format": "float", "description": "Start longitude"},
        "start_node_id": {"type": "integer", "description": "Start node ID"},
        "start_region_code": {"type": "string", "description": "Start region code"},
        "start_geom": {"type": "string", "nullable": True, "description": "Start geometry"},
        "end_area_code": {"type": "string", "description": "End area code"},
        "end_lat": {"type": "number", "format": "float", "description": "End latitude"},
        "end_lon": {"type": "number", "format": "float", "description": "End longitude"},
        "end_node_id": {"type": "integer", "description": "End node ID"},
        "end_region_code": {"type": "string", "description": "End region code"},
        "end_geom": {"type": "string", "nullable": True, "description": "End geometry"},
        "total_bus_distance": {"type": "integer", "description": "Total bus distance in meters"},
        "transfers": {"type": "integer", "description": "Number of transfers"},
        "transit_time": {"type": "integer", "description": "Transit time in seconds"},
        "waiting_time": {"type": "integer", "description": "Waiting time in seconds"},
        "12kmh_total_duration": {"type": "integer", "description": "total trip time at 12km/h total duration in seconds"},
        "12kmh_total_bus_duration": {"type": "integer","description": "total time spent on bus at 12km/h total duration in seconds"},
        "30kmh_total_duration": {"type": "integer", "description": "total trip time at 30km/h total duration in seconds"},
        "30kmh_total_bus_duration": {"type": "integer","description": "total time spent on bus at 30km/h total duration in seconds"},
        "48kmh_total_duration": {"type": "integer","description": "total trip time at 48km/h total duration in seconds"},
        "48kmh_total_bus_duration": {"type": "integer","description": "total time spent on bus at 48km/h total duration in seconds"},
        "5kmh_total_duration": {"type": "integer","description": "total trip time at 5km/h total duration in seconds"},
        "5kmh_total_bus_duration": {"type": "integer","description": "total time spent on bus at 5km/h total duration in seconds"},
        "non_bus_duration": {"type": "integer","description": "Total time spent not on a bus in seconds"},
        "non_flooded_total_duration": {"type": "integer", "description": "Total trip time in seconds at 60km/h"},
        "non_flooded_total_bus_duration": {"type": "integer", "description": "Total time spent on bus at 60km/h"},
        "number_of_busroutes": {"type": "integer","description": "Number of buses taken"},
        "routeNodeIDs": {"type": "array", "items": {"type": "integer"}, "description": "List of route node IDs on OSMNX graph"},
        "filepath": {"type": "string", "description": "Filepath to detailed trip data in json format"}
    }
}

bus_trip_segment_schema = {
    "type": "object",
    "properties": {
        "12kmh_flooded_bus_duration": {"type": "integer", "description": "Duration at 12km/h in flooded conditions"},
        "30kmh_flooded_bus_duration": {"type": "integer", "description": "Duration at 30km/h in flooded conditions"},
        "48kmh_flooded_bus_duration": {"type": "integer", "description": "Duration at 48km/h in flooded conditions"},
        "5kmh_flooded_bus_duration": {"type": "integer", "description": "Duration at 5km/h in flooded conditions"},
        "bus_trip_id": {"type": "integer", "description": "Bus trip ID"},
        "destination_stop_id": {"type": "string", "description": "ID of the destination stop"},
        "filepath": {"type": "string", "description": "Filepath of the segment data"},
        "non_flooded_bus_duration": {"type": "integer", "description": "Duration in non-flooded conditions"},
        "origin_stop_id": {"type": "string", "description": "ID of the origin stop"},
        "route_id": {"type": "string", "description": "ID of the route"},
        "segment": {"type": "integer", "description": "Segment number"}
    },
    "required": ["bus_trip_id", "origin_stop_id", "destination_stop_id", "segment"]
}

bus_delayed_schema = {"type": "object",
    "properties": {
        "trips": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "bus_trip_id": {"type": "integer", "description": "Bus trip ID"},
                    "start_lat": {"type": "number", "format": "float", "description": "Start latitude"},
                    "start_lon": {"type": "number", "format": "float", "description": "Start longitude"},
                    "end_lat": {"type": "number", "format": "float", "description": "End latitude"},
                    "end_lon": {"type": "number", "format": "float", "description": "End longitude"},
                    "flooded_total_bus_durations": {
                        "type": "object",
                        "properties": {
                            "12kmh": {"type": "integer", "description": "Total bus duration at 12km/h"},
                            "30kmh": {"type": "integer", "description": "Total bus duration at 30km/h"},
                            "48kmh": {"type": "integer", "description": "Total bus duration at 48km/h"},
                            "5kmh": {"type": "integer", "description": "Total bus duration at 5km/h"}
                        }
                    },
                    "flooded_total_durations": {
                        "type": "object",
                        "properties": {
                            "12kmh": {"type": "integer", "description": "Total duration at 12km/h"},
                            "30kmh": {"type": "integer", "description": "Total duration at 30km/h"},
                            "48kmh": {"type": "integer", "description": "Total duration at 48km/h"},
                            "5kmh": {"type": "integer", "description": "Total duration at 5km/h"}
                        }
                    },
                    "non_flooded_total_bus_duration": {"type": "integer", "description": "Non-flooded total bus duration"},
                    "non_flooded_total_duration": {"type": "integer", "description": "Non-flooded total duration"},
                    "overall_bus_delay": {
                        "type": "object",
                        "properties": {
                            "12kmh": {"type": "integer", "description": "Overall bus delay at 12km/h"},
                            "30kmh": {"type": "integer", "description": "Overall bus delay at 30km/h"},
                            "48kmh": {"type": "integer", "description": "Overall bus delay at 48km/h"},
                            "5kmh": {"type": "integer", "description": "Overall bus delay at 5km/h"}
                        }
                    },
                    "overall_total_delay": {
                        "type": "object",
                        "properties": {
                            "12kmh": {"type": "integer", "description": "Overall total delay at 12km/h"},
                            "30kmh": {"type": "integer", "description": "Overall total delay at 30km/h"},
                            "48kmh": {"type": "integer", "description": "Overall total delay at 48km/h"},
                            "5kmh": {"type": "integer", "description": "Overall total delay at 5km/h"}
                        }
                    },
                    "segments": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "segment_id": {"type": "integer", "description": "Segment ID"},
                                "origin_stop_id": {"type": "string", "description": "Origin stop ID"},
                                "destination_stop_id": {"type": "string", "description": "Destination stop ID"},
                                "non_flooded_bus_duration": {"type": "integer", "description": "Non-flooded bus duration"},
                                "flooded_durations": {
                                    "type": "object",
                                    "properties": {
                                        "12kmh": {"type": "integer", "description": "Flooded Individual Bus duration at 12km/h"},
                                        "30kmh": {"type": "integer", "description": "Flooded Individual Bus duration at 30km/h"},
                                        "48kmh": {"type": "integer", "description": "Flooded Individual Bus duration at 48km/h"},
                                        "5kmh": {"type": "integer", "description": "Flooded Individual Bus duration at 5km/h"}
                                    }
                                },
                                "delays": {
                                    "type": "object",
                                    "properties": {
                                        "12kmh": {"type": "integer", "description": "Bus segment Flooded delay at 12km/h"},
                                        "30kmh": {"type": "integer", "description": "Bus segment Flooded delay at 30km/h"},
                                        "48kmh": {"type": "integer", "description": "Bus segment Flooded delay at 48km/h"},
                                        "5kmh": {"type": "integer", "description": "Bus segment Flooded delay at 5km/h"}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}