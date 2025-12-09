"""Unit tests for storage service."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from src.web.storage import (
    StorageService,
    StorageConfig,
    FileValidationError,
    PDFValidationError,
    DiskSpaceError,
)


@pytest.fixture
def temp_dirs(tmp_path):
    """Create temporary directories for testing."""
    StorageConfig.upload_dir = tmp_path / "uploads"
    StorageConfig.output_dir = tmp_path / "output"
    StorageConfig.temp_dir = tmp_path / "temp"
    StorageConfig.init()
    return tmp_path


@pytest.fixture
def storage_service():
    """Create storage service instance."""
    return StorageService()


@pytest.fixture
def valid_pdf_content():
    """Generate valid PDF-like content."""
    # Minimal PDF header with enough content to pass minimum size check
    return b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n" + b"x" * 2000  # Make it > 1KB


@pytest.fixture
def async_file_chunks(valid_pdf_content):
    """Create async iterator of file chunks."""
    async def _chunks():
        chunk_size = 1024
        for i in range(0, len(valid_pdf_content), chunk_size):
            yield valid_pdf_content[i:i + chunk_size]
    return _chunks()


class TestStorageService:
    """Test StorageService functionality."""

    @pytest.mark.asyncio
    async def test_save_upload_success(self, storage_service, temp_dirs, async_file_chunks):
        """Test successful file upload."""
        result = await storage_service.save_upload(
            async_file_chunks,
            "test.pdf",
            expected_size=None
        )

        file_path, file_hash, file_size = result
        assert Path(file_path).exists()
        assert file_hash
        assert file_size > 0
        assert "test.pdf" in file_path

    @pytest.mark.asyncio
    async def test_save_upload_invalid_extension(self, storage_service):
        """Test upload with invalid file extension."""
        async def bad_chunks():
            yield b"test content"

        with pytest.raises(FileValidationError) as exc:
            await storage_service.save_upload(
                bad_chunks(),
                "test.txt",
                expected_size=None
            )
        assert "Invalid filename" in str(exc.value)

    @pytest.mark.asyncio
    async def test_save_upload_size_limit(self, storage_service, temp_dirs):
        """Test file size limit enforcement."""
        StorageConfig.max_file_size = 100  # 100 bytes limit

        async def large_chunks():
            for _ in range(10):
                yield b"x" * 50  # 500 bytes total

        with pytest.raises(FileValidationError) as exc:
            await storage_service.save_upload(
                large_chunks(),
                "large.pdf",
                expected_size=None
            )
        assert "exceeds maximum size" in str(exc.value)

    @pytest.mark.asyncio
    async def test_save_upload_size_mismatch(self, storage_service, temp_dirs, valid_pdf_content):
        """Test expected size validation."""
        async def chunks():
            yield valid_pdf_content

        with pytest.raises(FileValidationError) as exc:
            await storage_service.save_upload(
                chunks(),
                "test.pdf",
                expected_size=100  # Wrong size - much smaller than actual
            )
        assert "mismatch" in str(exc.value) or "exceeds" in str(exc.value)

    @pytest.mark.asyncio
    async def test_validate_pdf_success(self, storage_service, temp_dirs):
        """Test successful PDF validation."""
        # Create a mock PDF file
        upload_dir = temp_dirs / "uploads"
        upload_dir.mkdir(exist_ok=True)
        pdf_path = upload_dir / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\ntest content")

        with patch("src.web.storage.service._validate_pdf_sync") as mock_validate:
            mock_validate.return_value = {
                "pages": 10,
                "encrypted": False,
                "has_metadata": True,
            }

            result = await storage_service.validate_pdf(str(pdf_path))
            assert result["pages"] == 10
            assert not result["encrypted"]

    @pytest.mark.asyncio
    async def test_validate_pdf_not_found(self, storage_service):
        """Test PDF validation with missing file."""
        with pytest.raises(PDFValidationError) as exc:
            await storage_service.validate_pdf("/nonexistent/file.pdf")
        assert "not found" in str(exc.value)

    @pytest.mark.asyncio
    async def test_validate_pdf_invalid(self, storage_service, temp_dirs):
        """Test validation of invalid PDF."""
        upload_dir = temp_dirs / "uploads"
        upload_dir.mkdir(exist_ok=True)
        pdf_path = upload_dir / "bad.pdf"
        pdf_path.write_bytes(b"not a pdf")

        with patch("src.web.storage.service._validate_pdf_sync") as mock_validate:
            from pypdf.errors import PdfReadError
            mock_validate.side_effect = PdfReadError("Invalid PDF")

            with pytest.raises(PDFValidationError) as exc:
                await storage_service.validate_pdf(str(pdf_path))
            assert "Invalid PDF" in str(exc.value)

    @pytest.mark.asyncio
    async def test_delete_file_success(self, storage_service, temp_dirs):
        """Test successful file deletion."""
        upload_dir = temp_dirs / "uploads"
        upload_dir.mkdir(exist_ok=True)
        file_path = upload_dir / "delete_me.pdf"
        file_path.write_bytes(b"content")

        result = await storage_service.delete_file(str(file_path))
        assert result is True
        assert not file_path.exists()

    @pytest.mark.asyncio
    async def test_delete_file_missing_ignored(self, storage_service):
        """Test deletion of missing file with ignore flag."""
        result = await storage_service.delete_file(
            "/nonexistent/file.pdf",
            ignore_missing=True
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_file_missing_error(self, storage_service):
        """Test deletion of missing file without ignore flag."""
        from src.web.storage.exceptions import FileOperationError

        with pytest.raises(FileOperationError) as exc:
            await storage_service.delete_file(
                "/nonexistent/file.pdf",
                ignore_missing=False
            )
        assert "not found" in str(exc.value)

    @pytest.mark.asyncio
    async def test_get_file_info(self, storage_service, temp_dirs):
        """Test file info retrieval."""
        upload_dir = temp_dirs / "uploads"
        upload_dir.mkdir(exist_ok=True)
        file_path = upload_dir / "info.pdf"
        content = b"test content"
        file_path.write_bytes(content)

        info = await storage_service.get_file_info(str(file_path))
        assert info["name"] == "info.pdf"
        assert info["size"] == len(content)
        assert info["extension"] == ".pdf"
        assert "created" in info
        assert "modified" in info

    @pytest.mark.asyncio
    async def test_generate_output_path(self, storage_service):
        """Test MSF output path generation."""
        path = storage_service.generate_output_path(
            "abc123def456",
            "Fluke 8846A"
        )
        assert "Fluke_8846A" in path
        assert "abc123de" in path  # First 8 chars of job ID
        assert path.endswith(".msf")

    @pytest.mark.asyncio
    async def test_generate_output_path_sanitization(self, storage_service):
        """Test output path with special characters."""
        path = storage_service.generate_output_path(
            "xyz789",
            "Test/Device@#$%"
        )
        assert "Test_Device____" in path
        assert "/" not in Path(path).name
        assert "@" not in Path(path).name

    @pytest.mark.asyncio
    async def test_disk_space_error(self, storage_service, temp_dirs):
        """Test disk space error handling."""
        # Set a smaller max file size for this test
        original_max = StorageConfig.max_file_size
        StorageConfig.max_file_size = 100000  # 100KB

        async def chunks():
            yield b"x" * 2000  # Bigger than min but small enough

        with patch("shutil.move") as mock_move:
            mock_move.side_effect = OSError("No space left on device")

            try:
                with pytest.raises(DiskSpaceError) as exc:
                    await storage_service.save_upload(
                        chunks(),
                        "test.pdf",
                        expected_size=None
                    )
                assert "Insufficient disk space" in str(exc.value)
            finally:
                StorageConfig.max_file_size = original_max

    @pytest.mark.asyncio
    async def test_cleanup_temp_on_error(self, storage_service, temp_dirs):
        """Test temporary file cleanup on error."""
        async def bad_chunks():
            yield b"test"
            raise Exception("Stream error")

        try:
            await storage_service.save_upload(
                bad_chunks(),
                "test.pdf",
                expected_size=None
            )
        except Exception:
            pass

        # Check temp files are cleaned up
        temp_files = list(StorageConfig.temp_dir.glob("*.tmp"))
        assert len(temp_files) == 0