from app.services.reporting import (
    get_latest_preferred_run,
    list_block_attachments,
    run_block,
    run_page,
    summarize_page_status,
)


# Backward-compatible names from stage 1

def execute_block(db, block, run_type="manual"):
    return run_block(db, block.id, run_type=run_type)


def execute_page_blocks(db, page_id: int, run_type: str = "manual"):
    result = run_page(db, page_id, run_type=run_type)
    return result["runs"]
