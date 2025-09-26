bus_stops_example = [
    {
        "stop_code": "98281",
        "stop_id": "98281",
        "stop_lat": 103.966171624349,
        "stop_lon": 1.35967915316721,
        "stop_name": "Estella Gdns",
        "stop_desc": None,
        "wheelchair_boarding": 1,
        "geom": None,
    },
    {
        "stop_code": "59629",
        "stop_id": "59629",
        "stop_lat": 1.434758706,
        "stop_lon": 103.8439165,
        "stop_name": "Symphony Suites Condo",
        "stop_desc": None,
        "wheelchair_boarding": 1,
        "geom": None,
    },
]

bus_stop_get_example = {
    "stop_code": "98281",
    "stop_id": "98281",
    "stop_lat": 103.966171624349,
    "stop_lon": 1.35967915316721,
    "stop_name": "Estella Gdns",
    "stop_desc": None,
    "wheelchair_boarding": "1",
    "geom": None
}


bus_trips_get_example ={
    "12kmh_total_bus_duration": 240,
    "12kmh_total_duration": 2185,
    "30kmh_total_bus_duration": 212,
    "30kmh_total_duration": 2157,
    "48kmh_total_bus_duration": 205,
    "48kmh_total_duration": 2150,
    "5kmh_total_bus_duration": 303,
    "5kmh_total_duration": 2248,
    "bus_trip_id": 13,
    "end_area_code": "PG",
    "end_geom": None,
    "end_lat": 1.40544909693222,
    "end_lon": 103.908503032429,
    "end_node_id": 2274884501,
    "end_region_code": "NER",
    "filepath": "01012to2274884501.json",
    "non_bus_duration": 1945,
    "non_flooded_total_bus_duration": 203,
    "non_flooded_total_duration": 2148,
    "number_of_busroutes": 1,
    "routeNodeIDs": [
        4738400701, 233432515, 233432542, 595267994, 595268007,
        233432563, 233432607, 233432633, 365302308, 233432671,
        5982556742, 4602210048, 233432705, 233432799, 7043294787,
        233432823, 5166520742, 249392291, 240646599, 249392296,
        240646581, 378619193, 378618810, 240646389, 240646408,
        236310575, 236320394, 2948839129, 229576235, 245396647,
        5243487086, 229576256, 377553457
    ],
    "start_area_code": "RC",
    "start_geom": None,
    "start_lat": 1.29684825487647,
    "start_lon": 103.85253591654,
    "start_node_id": 4748705954,
    "start_region_code": "CR",
    "total_bus_distance": 3388,
    "transfers": 2,
    "transit_time": 1860,
    "waiting_time": 366
}


bus_trip_segment_example = {
    "12kmh_flooded_bus_duration": 240,
    "30kmh_flooded_bus_duration": 212,
    "48kmh_flooded_bus_duration": 205,
    "5kmh_flooded_bus_duration": 303,
    "bus_trip_id": 13,
    "destination_stop_id": "60121",
    "filepath": "01012to2274884501.json",
    "non_flooded_bus_duration": 203,
    "origin_stop_id": "01013",
    "route_id": "133",
    "segment": 1
}

bus_trips_delayed_example = {
    "trips": [
        {
            "bus_trip_id": 5,
            "start_lat": 1.29684825487647,
            "start_lon": 103.85253591654,
            "end_lat": 1.35537955952137,
            "end_lon": 103.887346108709,
            "flooded_total_bus_durations": {
                "12kmh": 240,
                "30kmh": 212,
                "48kmh": 205,
                "5kmh": 303
            },
            "flooded_total_durations": {
                "12kmh": 2002,
                "30kmh": 1974,
                "48kmh": 1967,
                "5kmh": 2065
            },
            "non_flooded_total_bus_duration": 203,
            "non_flooded_total_duration": 1965,
            "overall_bus_delay": {
                "12kmh": 37,
                "30kmh": 9,
                "48kmh": 2,
                "5kmh": 100
            },
            "overall_total_delay": {
                "12kmh": 37,
                "30kmh": 9,
                "48kmh": 2,
                "5kmh": 100
            },
            "segments": [
                {
                    "segment_id": 1,
                    "origin_stop_id": "01013",
                    "destination_stop_id": "60121",
                    "non_flooded_bus_duration": 203,
                    "flooded_durations": {
                        "12kmh": 240,
                        "30kmh": 212,
                        "48kmh": 205,
                        "5kmh": 303
                    },
                    "delays": {
                        "12kmh": 37,
                        "30kmh": 9,
                        "48kmh": 2,
                        "5kmh": 100
                    }
                }
            ]
        }
    ]
}