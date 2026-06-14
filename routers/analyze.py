from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.vision_service import get_scene

router = APIRouter(prefix="/analyze", tags=["Analyze"])


class AnalyzeRequest(BaseModel):
    frame_base64: str


@router.post("")
async def analyze_scene(request: AnalyzeRequest):
    """Analyze a frame and return the raw scene graph without running agents."""
    try:
        scene = await get_scene(request.frame_base64)
        return scene.model_dump()
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Analysis failed: {e}")
