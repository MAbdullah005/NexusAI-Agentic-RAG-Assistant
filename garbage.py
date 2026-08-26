
# GENErate thread title
#@router.post('get-thread-title')
#def get_thread_title_db(thread_id: str) -> str:
#    try:
#        cursor = conn.cursor()

 #       cursor.execute(
  #      SELECT title FROM threads WHERE thread_id=?
        #, (thread_id,))

        #row = cursor.fetchone()

       # if row and row[0]:
 #           return row[0]

  #      return f"Chat {thread_id[:6]}"

#    except Exception as e:
 #       logger.error(f"Failed to get thread title: {str(e)}")
  #      return f"Chat {thread_id[:6]}"


# save thread title 

#@router.post('save-thread-title')
#def save_thread_title_api(thread_id: str, title: str):
 #   try:
 #       cursor = conn.cursor()

       # cursor.execute(
       # INSERT INTO threads (thread_id, title)
       # VALUES (?, ?)
        #ON CONFLICT(thread_id)
        #DO UPDATE SET title=excluded.title
        #, (thread_id, title))

#        conn.commit()

 #   except Exception as e:
  #      logger.error(f"Failed to save thread title: {str(e)}")




# getpdf 

#''''''''''''''''''
""""
@router.get("/get_pdf/{thread_id}")
def get_pdf(
    thread_id: str,
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["user_id"]

    cursor = conn.cursor()

    # ==========================================
    # Verify thread ownership
    # ==========================================

    cursor.execute(
    
        SELECT thread_id
        FROM threads
        WHERE thread_id = ?
          AND user_id = ?
        
        (thread_id, user_id)
    )

    thread = cursor.fetchone()

    if thread is None:
        raise HTTPException(
            status_code=404,
            detail="Thread not found"
        )

    # ==========================================
    # Get PDF belonging to this thread
    # ==========================================

    cursor.execute(
        
        SELECT d.source
        FROM documents d
        JOIN thread_documents td
            ON d.doc_id = td.doc_id
        WHERE td.thread_id = ?
          AND d.user_id = ?
          AND d.type = 'pdf'
        ORDER BY d.created_at DESC
        ,
        (thread_id, user_id)
    )

    row = cursor.fetchone()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="No PDF found for this thread"
        )

    file_path = row[0]

    # ==========================================
    # Verify physical file exists
    # ==========================================

    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=404,
            detail="PDF file not found"
        )

    # ==========================================
    # Return PDF
    # ==========================================

    return FileResponse(
        file_path,
        media_type="application/pdf"
    )
"""