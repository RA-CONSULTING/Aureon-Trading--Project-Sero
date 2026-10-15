import json

from organism.public_market import SOURCE, observe_public_price


def test_public_price_records_the_ticker_and_places_no_order():
    body = json.dumps({"symbol": "BTCUSDT", "price": "81290.01000000"}).encode()

    observed = observe_public_price(lambda url: body if url == SOURCE else (_ for _ in ()).throw(ValueError(url)))

    assert observed["symbol"] == "BTCUSDT"
    assert observed["price"] == "81290.01000000"
    assert observed["order_count"] == 0
    assert observed["generated_values"] is False
    assert observed["may_act"] is False
    assert observed["source"] == SOURCE
