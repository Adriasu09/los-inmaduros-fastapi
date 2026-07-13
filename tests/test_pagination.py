from src.common.pagination import build_pagination


def test_zero_results_yields_zero_pages_and_no_navigation():
    block = build_pagination(page=1, limit=20, total_count=0)

    assert block.total_pages == 0
    assert block.has_next_page is False
    assert block.has_previous_page is False


def test_single_page_has_no_navigation():
    block = build_pagination(page=1, limit=20, total_count=5)

    assert block.total_pages == 1
    assert block.has_next_page is False
    assert block.has_previous_page is False


def test_first_of_several_pages_only_has_next():
    block = build_pagination(page=1, limit=10, total_count=25)

    assert block.total_pages == 3
    assert block.has_next_page is True
    assert block.has_previous_page is False


def test_middle_page_has_both_directions():
    block = build_pagination(page=2, limit=10, total_count=25)

    assert block.has_next_page is True
    assert block.has_previous_page is True


def test_last_page_only_has_previous():
    # The checkpoint case: 45 items, 20 per page -> page 3 IS the last page
    block = build_pagination(page=3, limit=20, total_count=45)

    assert block.model_dump(by_alias=True) == {
        "page": 3,
        "limit": 20,
        "totalCount": 45,
        "totalPages": 3,
        "hasNextPage": False,
        "hasPreviousPage": True,
    }


def test_exact_division_does_not_create_an_empty_extra_page():
    # 40/20 = exactly 2 pages; ceil must not round up to 3
    block = build_pagination(page=2, limit=20, total_count=40)

    assert block.total_pages == 2
    assert block.has_next_page is False
