"""Build immutable song features into the image, not on the small web CPU."""
from backend.app.config import Settings
from backend.app.scoring.service import ScoringService
from backend.app.services.song_catalog import SongCatalog


def main() -> None:
    settings = Settings()
    catalog = SongCatalog(settings.song_manifest_path, settings.repository_root)
    scoring = ScoringService()
    for public in catalog.all_public():
        song = catalog.get(public.id)
        path = catalog.asset_path(song.reference_vocal_path)
        scoring.prepare_reference(path)
        # Also compile comparison kernels using the same production pipeline.
        scoring.analyze(reference_vocal_path=path, player_vocal_path=path,
                        expected_lyrics=song.expected_lyrics, detected_lyrics=song.expected_lyrics,
                        transcript_source="elevenlabs")
        print(f"Prepared reference: {song.id}", flush=True)


if __name__ == "__main__":
    main()
