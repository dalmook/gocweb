from app.services.run_service import run_block, run_page


def execute_block(db, block, run_type="manual"):
    return run_block(db, block.id, run_type=run_type)


def execute_page_blocks(db, page_id: int, run_type: str = "manual"):
    return run_page(db, page_id, run_type=run_type)["runs"]
