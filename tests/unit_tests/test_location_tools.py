from langchain_core.messages import HumanMessage

import agent.custom_tools.location_tools as location_tools
from agent.custom_tools.location_tools import (
    extract_place_type,
    extract_place_types,
    get_location_info_sync,
    location_fallback_response,
    wants_location,
)
from agent.graph import _pick_route
from agent.routing import is_math_query, pick_tool_choice


def test_location_intent_detection() -> None:
    assert wants_location("Where am I?")
    assert wants_location("Nearby hospitals")
    assert wants_location("Find petrol pumps near me")
    assert not wants_location("Calculate 2 + 2")
    assert not is_math_query("Find nearby restaurants open 24/7")


def test_extract_supported_place_types() -> None:
    assert extract_place_type("nearby restaurants") == "restaurant"
    assert extract_place_type("show nearby ATMs") == "atm"
    assert extract_place_type("petrol pumps near me") == "fuel"
    assert extract_place_type("shopping malls around me") == "shopping_mall"
    assert extract_place_type("supermarkets nearby") == "supermarket"


def test_extract_multiple_place_types() -> None:
    assert extract_place_types("nearby restaurants and pharmacies") == [
        "restaurant",
        "pharmacy",
    ]


def test_missing_coordinates_returns_friendly_message() -> None:
    assert location_fallback_response("Where am I?") == (
        "I need your location to help with this request. "
        "Please allow location access in your browser/device and try again."
    )


def test_location_response_is_natural_language(monkeypatch) -> None:
    monkeypatch.setattr(
        location_tools,
        "reverse_geocode",
        lambda latitude, longitude: {
            "formatted_address": "123 Test Road, Test City",
            "city": "Test City",
            "state": "Test State",
            "country": "Test Country",
            "postal_code": "12345",
        },
    )
    monkeypatch.setattr(
        location_tools,
        "search_nearby_places",
        lambda latitude, longitude, place_type: [
            {
                "name": f"Test {place_type.title()}",
                "type": place_type,
                "address": "Nearby Street",
                "distance": "0.25 km",
                "distance_km": 0.25,
                "latitude": 24.1,
                "longitude": 67.1,
            }
        ],
    )

    response = location_fallback_response(
        "Where am I, and show nearby restaurants and pharmacies",
        24.0,
        67.0,
    )

    assert response.startswith("Here is what I found from OpenStreetMap:")
    assert "Address: 123 Test Road, Test City" in response
    assert "Test Restaurant" in response
    assert "Test Pharmacy" in response


def test_location_info_has_osm_structured_data(monkeypatch) -> None:
    monkeypatch.setattr(
        location_tools,
        "reverse_geocode",
        lambda latitude, longitude: {
            "formatted_address": "123 Test Road, Test City",
            "city": "Test City",
            "state": "Test State",
            "country": "Test Country",
            "postal_code": "12345",
        },
    )
    monkeypatch.setattr(
        location_tools,
        "search_nearby_places",
        lambda latitude, longitude, place_type: [],
    )

    payload = get_location_info_sync(24.0, 67.0, "Where am I?")

    assert payload["current_location"]["latitude"] == 24.0
    assert payload["current_location"]["city"] == "Test City"
    assert payload["nearby_places"] == []


def test_graph_routes_location_queries_to_location_node() -> None:
    route = _pick_route(
        "Nearby pharmacies",
        [HumanMessage(content="Nearby pharmacies")],
    )
    assert route == "run_location"


def test_location_route_wins_over_math_like_text() -> None:
    text = "Find nearby restaurants open 24/7"

    route = _pick_route(text, [HumanMessage(content=text)])

    assert route == "run_location"
    assert pick_tool_choice(text) == {
        "type": "function",
        "function": {"name": "get_live_location"},
    }
