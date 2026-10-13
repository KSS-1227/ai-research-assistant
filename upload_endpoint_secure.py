# Secure upload endpoint - to be integrated into fastapi_app.py

@app.post("/upload", response_model=UploadResponse, tags=["Documents"])
@limiter.limit("5/minute")
async def upload_documents(
    request: Request,
    files: List[UploadFile] = File(...),
    sm: SessionManager = Depends(get_session_manager),
) -> UploadResponse:
    """Upload research documents. Creates a new session."""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    # Task 5: Reject early if too many files
    if len(files) > MAX_FILES_PER_UPLOAD:
        raise HTTPException(
            status_code=400,
            detail=f"Too many files. Maximum {MAX_FILES_PER_UPLOAD} files per upload."
        )

    # Task 5: Validate file sizes before creating session
    allowed_extensions = {".pdf", ".txt", ".md"}
    for file in files:
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in allowed_extensions:
            continue
        if hasattr(file, "size") and file.size and file.size > 50 * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail=f"File {file.filename} exceeds 50 MB limit"
            )

    # Create session only after basic validation passes
    session = sm.create_session()
    session.temp_dir = tempfile.mkdtemp(prefix=f"research_{session.session_id}_")

    supported_files = []
    unsupported_files = []
    total_size_mb = 0.0
    seen_names = set()

    try:
        for file in files:
            file_ext = Path(file.filename).suffix.lower()

            if file_ext not in allowed_extensions:
                unsupported_files.append(file.filename)
                continue

            # Task 1: Sanitize filename
            try:
                safe_name = _sanitize_filename(file.filename)
            except HTTPException:
                unsupported_files.append(f"{file.filename} (invalid name)")
                continue
            
            # Task 1: Handle duplicate names
            if safe_name in seen_names:
                prefix = secrets.token_hex(4)
                safe_name = f"{prefix}_{safe_name}"
            seen_names.add(safe_name)

            # Task 5: Read file in chunks
            contents = b""
            chunk_size = 1024 * 1024
            bytes_read = 0
            max_bytes = 50 * 1024 * 1024
            
            try:
                while True:
                    chunk = await file.read(chunk_size)
                    if not chunk:
                        break
                    bytes_read += len(chunk)
                    if bytes_read > max_bytes:
                        raise HTTPException(
                            status_code=400,
                            detail=f"File {file.filename} exceeds 50 MB limit"
                        )
                    contents += chunk
            except HTTPException:
                raise
            
            size_mb = len(contents) / (1024 * 1024)

            # Task 1: Build path and assert it's inside temp_dir
            file_path = os.path.join(session.temp_dir, safe_name)
            _assert_path_inside_dir(file_path, session.temp_dir)
            
            with open(file_path, "wb") as f:
                f.write(contents)

            supported_files.append(safe_name)
            total_size_mb += size_mb
            session.documents_uploaded += 1
            doc_id = secrets.token_hex(4)
            session.uploaded_files[doc_id] = DocumentInfo(
                document_id=doc_id,
                filename=safe_name,
                uploaded_at=datetime.now().isoformat(),
                size_kb=round(size_mb * 1024, 2),
            )

        if not supported_files:
            sm.delete_session(session.session_id)
            raise HTTPException(
                status_code=400,
                detail="No valid files. Supported: .pdf, .txt, .md"
            )

        logger.info(
            f"Session {session.session_id}: uploaded {len(supported_files)} files "
            f"({total_size_mb:.2f} MB)"
        )

        return UploadResponse(
            session_id=session.session_id,
            file_count=len(supported_files),
            total_size_mb=round(total_size_mb, 3),
            supported_files=supported_files,
            unsupported_files=unsupported_files,
            message=f"Uploaded {len(supported_files)} file(s). Next: POST /process",
        )

    except HTTPException:
        raise
    except Exception as e:
        sm.delete_session(session.session_id)
        logger.error(f"Upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
