from fastapi import APIRouter
from fastapi.responses import RedirectResponse

router = APIRouter()


@router.get("/")
def home_redirect():
    return RedirectResponse("/admin", status_code=302)
