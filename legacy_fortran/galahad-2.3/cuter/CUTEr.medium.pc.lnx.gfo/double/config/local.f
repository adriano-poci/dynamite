C     ( Last modified on 23 Dec 2000 at 22:01:38 )
      SUBROUTINE HASHA ( LENGTH, ITABLE )
      INTEGER          LENGTH
      INTEGER          ITABLE( LENGTH )
      COMMON / HASHZ  / DPRIME, IEMPTY
      INTEGER          IEMPTY
      DOUBLE PRECISION DPRIME
C
C  SET UP INITIAL SCATTER TABLE (WILLIAMS, CACM 2, 21-24, 1959).
C
C  ITABLE( I ) GIVES THE STATUS OF TABLE ENTRY I.
C  IF STATUS = - ( LENGTH + 1 ), THE ENTRY IS UNUSED.
C
C  NICK GOULD, FOR CGT PRODUCTIONS.
C  4TH JULY 1989.
C
      INTEGER  I, IPRIME
      EXTERNAL HASHF
      LOGICAL  HASHF, PRIME
      IEMPTY  = LENGTH + 1
C
C  FIND AN APPROPRIATE PRIME NUMBER FOR THE HASH FUNCTION.
C  COMPUTE THE LARGEST PRIME SMALLER THAN LENGTH.
C
      IPRIME = 2 * ( ( LENGTH + 1 ) / 2 ) - 1
   10 CONTINUE
C
C  IS IPRIME PRIME?
C
      PRIME = HASHF ( IPRIME )
      IF ( .NOT. PRIME ) THEN
         IPRIME = IPRIME - 2
         GO TO 10
      END IF
      DPRIME = IPRIME
C
C  INITIALIZE EACH TABLE ENTRY AS UNFILLED.
C
      DO 20 I        = 1, LENGTH
         ITABLE( I ) = - IEMPTY
   20 CONTINUE
      RETURN
C
C  END OF HASHA.
C
      END
C
C
C
      SUBROUTINE HASHB ( LENGTH, NCHAR, FIELD, KEY, ITABLE, IFREE )
      INTEGER          NCHAR, IFREE, LENGTH
      INTEGER          ITABLE( LENGTH )
      CHARACTER * 1    FIELD( NCHAR ), KEY( NCHAR, LENGTH )
      COMMON / HASHZ  / DPRIME, IEMPTY
      INTEGER          IEMPTY
      DOUBLE PRECISION DPRIME
C
C  INSERT IN CHAINED SCATTER TABLE (WILLIAMS, CACM 2, 21-24, 1959).
C
C  ITABLE( I ) GIVES THE STATUS OF TABLE ENTRY I.
C  IF STATUS = - ( LENGTH + 1 ), THE ENTRY IS UNUSED.
C  IF STATUS = - K, THE ENTRY WAS USED BUT HAS BEEN DELETED. K GIVES
C              THE INDEX OF THE NEXT ENTRY IN THE CHAIN.
C  IF STATUS = 0, THE ENTRY IS USED AND LIES AT THE END OF A CHAIN.
C  IF STATUS = K, THE ENTRY IS USED. K GIVES THE INDEX OF THE NEXT
C              ENTRY IN THE CHAIN.
C  IFIELD( I ) GIVES THE FIELD KEY FOR USED ENTRIES IN THE TABLE.
C
C  NICK GOULD, FOR CGT PRODUCTIONS.
C  4TH JULY 1989.
C
      INTEGER          I, J, K, NBYTES, NOVER2
      PARAMETER      ( NBYTES =  8 )
      PARAMETER      ( NOVER2 = NBYTES / 2 )
      CHARACTER * 1    BFIELD( NBYTES )
      INTEGER          IVALUE( 2 )
      INTEGER          HASHE
      EXTERNAL         HASHE
      INTRINSIC        MOD, IDINT, IABS, ICHAR
C
C  FIND A STARTING POSITION, IFREE, FOR THE INSERTION.
C  PERFORM THE HASHING ON 8 CHARACTERS OF FIELD AT A TIME.
C
      IFREE      = 0
      DO 30 J    = 1, NCHAR, NBYTES
         DO 10 I = 1, NBYTES
            K    = J + I - 1
            IF ( K .LE. NCHAR ) THEN
               BFIELD( I ) = FIELD( K )
            ELSE
               BFIELD( I ) = ' '
            END IF
   10    CONTINUE
C
C  CONVERT THE CHARACTER STRING INTO TWO INTEGER NUMBERS.
C
         IVALUE( 1 ) = ICHAR( BFIELD( 1 ) ) / 2
         IVALUE( 2 ) = ICHAR( BFIELD( NOVER2 + 1 ) ) / 2
         DO 20 I = 2, NOVER2
            IVALUE( 1 ) = 256 * IVALUE( 1 ) + ICHAR( BFIELD( I ) )
            IVALUE( 2 ) = 256 * IVALUE( 2 ) +
     *                          ICHAR( BFIELD( NOVER2 + I ) )
   20    CONTINUE
C
C  CONVERT THE CHARACTER STRING INTO A DOUBLE PRECISION NUMBER.
C
C        READ( UNIT = FIELD8, FMT = 1000 ) VALUE
C
C  HASH AND ADD THE RESULT TO IFREE.
C
         IFREE = IFREE + HASHE ( IVALUE( 1 ), DPRIME )
   30 CONTINUE
C
C  ENSURE THAT IFREE LIES WITHIN THE ALLOWED RANGE.
C
      IFREE = MOD( IFREE, IDINT( DPRIME ) ) + 1
C
C  IS THERE A LIST?
C
      IF ( ITABLE( IFREE ) .GE. 0 ) THEN
C
C  COMPARE TO SEE IF THE KEY HAS BEEN FOUND.
C
   40    CONTINUE
         DO 50 I = 1, NCHAR
            IF ( FIELD( I ) .NE. KEY( I, IFREE ) ) GO TO 60
   50    CONTINUE
C
C  THE KEY ALREADY EXISTS AND THEREFORE CANNOT BE INSERTED.
C
         IF ( ITABLE( IFREE ) .GE. 0 ) THEN
            IFREE = - IFREE
            RETURN
         END IF
C
C  THE KEY USED TO EXIST BUT HAS BEEN DELETED AND MUST BE RESTORED.
C
         GO TO 100
C
C  ADVANCE ALONG THE CHAIN TO THE NEXT ENTRY.
C
   60    CONTINUE
         IF ( ITABLE( IFREE ) .NE. 0 ) THEN
            IFREE = IABS( ITABLE( IFREE ) )
            GO TO 40
         END IF
C
C  THE END OF THE CHAIN HAS BEEN REACHED. FIND EMPTY ENTRY IN THE TABLE.
C
   70    CONTINUE
         IEMPTY = IEMPTY - 1
         IF ( IEMPTY .EQ. 0 ) THEN
            IFREE = 0
            RETURN
         END IF
         IF ( ITABLE( IEMPTY ) .GE. - LENGTH ) GO TO 70
         ITABLE( IFREE ) = IEMPTY
         IFREE           = IEMPTY
      ELSE
C
C  THE STARTING ENTRY FOR THE CHAIN IS UNUSED.
C
         IF ( ITABLE( IFREE ) .GE. - LENGTH ) THEN
            ITABLE( IFREE ) = - ITABLE ( IFREE )
            GO TO 100
         END IF
      END IF
C
C  THERE IS NO LINK FROM THE NEWLY INSERTED FIELD.
C
      ITABLE( IFREE ) = 0
C
C  INSERT NEW KEY.
C
  100 CONTINUE
      DO 110 I            = 1, NCHAR
         KEY( I, IFREE ) = FIELD( I )
  110 CONTINUE
      RETURN
C
C  END OF HASHB.
C
      END
C
C
C
      SUBROUTINE HASHC ( LENGTH, NCHAR, FIELD, KEY, ITABLE, IFREE )
      INTEGER          LENGTH, NCHAR, IFREE
      INTEGER          ITABLE( LENGTH )
      CHARACTER * 1    FIELD( NCHAR ), KEY( NCHAR, LENGTH )
      COMMON / HASHZ  / DPRIME, IEMPTY
      INTEGER          IEMPTY
      DOUBLE PRECISION DPRIME
C
C  SEARCH WITHIN CHAINED SCATTER TABLE (WILLIAMS, CACM 2, 21-24, 1959).
C
C  ITABLE( I ) GIVES THE STATUS OF TABLE ENTRY I.
C  IF STATUS = - ( LENGTH + 1 ), THE ENTRY IS UNUSED.
C  IF STATUS = - K, THE ENTRY WAS USED BUT HAS BEEN DELETED. K GIVES
C              THE INDEX OF THE NEXT ENTRY IN THE CHAIN.
C  IF STATUS = 0, THE ENTRY IS USED AND LIES AT THE END OF A CHAIN.
C  IF STATUS = K, THE ENTRY IS USED. K GIVES THE INDEX OF THE NEXT
C              ENTRY IN THE CHAIN.
C  IFIELD( I ) GIVES THE FIELD KEY FOR USED ENTRIES IN THE TABLE.
C
C  NICK GOULD, FOR CGT PRODUCTIONS.
C  4TH JULY 1989.
C
      INTEGER          I, J, K, NBYTES, NOVER2
      PARAMETER      ( NBYTES =  8 )
      PARAMETER      ( NOVER2 = NBYTES / 2 )
      CHARACTER * 1    BFIELD( NBYTES )
      INTEGER          IVALUE( 2 )
      INTEGER          HASHE
      EXTERNAL         HASHE
      INTRINSIC        MOD, IDINT, IABS, ICHAR
C
C  FIND A STARTING POSITION, IFREE, FOR THE CHAIN LEADING TO THE
C  REQUIRED LOCATION.
C  PERFORM THE HASHING ON NBYTES CHARACTERS OF FIELD AT A TIME.
C
      IFREE      = 0
      DO 30 J    = 1, NCHAR, NBYTES
         DO 10 I = 1, NBYTES
            K    = J + I - 1
            IF ( K .LE. NCHAR ) THEN
               BFIELD( I ) = FIELD( K )
            ELSE
               BFIELD( I ) = ' '
            END IF
   10    CONTINUE
C
C  CONVERT THE CHARACTER STRING INTO TWO INTEGER NUMBERS.
C
         IVALUE( 1 ) = ICHAR( BFIELD( 1 ) ) / 2
         IVALUE( 2 ) = ICHAR( BFIELD( NOVER2 + 1 ) ) / 2
         DO 20 I = 2, NOVER2
            IVALUE( 1 ) = 256 * IVALUE( 1 ) + ICHAR( BFIELD( I ) )
            IVALUE( 2 ) = 256 * IVALUE( 2 ) +
     *                          ICHAR( BFIELD( NOVER2 + I ) )
   20    CONTINUE
C
C  CONVERT THE CHARACTER STRING INTO A DOUBLE PRECISION NUMBER.
C
C        READ( UNIT = FIELD8, FMT = 1000 ) VALUE
C
C  HASH AND ADD THE RESULT TO IFREE.
C
         IFREE = IFREE + HASHE ( IVALUE( 1 ), DPRIME )
   30 CONTINUE
C
C  ENSURE THAT IFREE LIES WITHIN THE ALLOWED RANGE.
C
      IFREE = MOD( IFREE, IDINT( DPRIME ) ) + 1
C
C  IS THERE A LIST?
C
      IF ( ITABLE( IFREE ) .LT. - LENGTH ) THEN
         IFREE = 0
         RETURN
      END IF
C
C  COMPARE TO SEE IF THE KEY HAS BEEN FOUND.
C
   40 CONTINUE
         DO 50 I = 1, NCHAR
            IF ( FIELD( I ) .NE. KEY( I, IFREE ) ) GO TO 60
   50    CONTINUE
C
C  CHECK THAT THE TABLE ITEM HAS NOT BEEN REMOVED.
C
         IF ( ITABLE( IFREE ) .LT. 0 ) THEN
            IFREE = - IFREE
         END IF
         RETURN
C
C  ADVANCE TO NEXT.
C
   60    CONTINUE
         IF ( ITABLE( IFREE ) .EQ. 0 ) THEN
            IFREE = 0
            RETURN
         END IF
         IFREE = IABS( ITABLE( IFREE ) )
      GO TO 40
      END
C
C  END OF HASHC.
C
C 
C
      INTEGER FUNCTION HASHE ( IVALUE, DPRIME )
      INTEGER IVALUE( 2 )
      DOUBLE PRECISION DPRIME
C
C  THE HASH FUNCTION (REID, 1976).
C  NICK GOULD, FOR CGT PRODUCTIONS.
C  4TH JULY 1989.
C
      INTRINSIC DMOD, DBLE, IABS
      HASHE  = DMOD( DBLE( IVALUE( 1 ) ) + IVALUE( 2 ), DPRIME )
      HASHE  = IABS( HASHE  ) + 1
      RETURN
C
C  END OF HASHE.
C
      END
C
C
C
      LOGICAL FUNCTION HASHF ( IPRIME )
      INTEGER IPRIME
C
C  RETURNS THE VALUE .TRUE. IF IPRIME IS PRIME.
C
C  NICK GOULD, FOR CGT PRODUCTIONS.
C  4TH JULY 1989.
C
      INTEGER I
      INTRINSIC MOD, DSQRT, INT, DBLE
      HASHF  = .FALSE.
      IF ( MOD( IPRIME, 2 ) .EQ. 0 ) RETURN
      DO 10 I = 3, INT( DSQRT( DBLE( IPRIME ) ) ), 2
         IF ( MOD( IPRIME, I ) .EQ. 0 ) RETURN
   10 CONTINUE
      HASHF  = .TRUE.
      RETURN
C
C  END OF HASHF.
C
      END
C
C
C
      REAL FUNCTION SMACHR( INUM )
      INTEGER       INUM
      REAL          RC( 5 )
C
C  REAL CONSTANTS (SINGLE PRECISION).
C
C  NICK GOULD, JULY 1988.
C
      DATA RC( 1 ) / 1.1920930E-07 /
      DATA RC( 2 ) / 5.9604646E-08 /
      DATA RC( 3 ) / 1.1754945E-38 /
      DATA RC( 4 ) / 1.1754945E-38 /
      DATA RC( 5 ) / 3.4028234E+38 /

      IF ( INUM .LE. 0 .OR. INUM .GE. 6 ) THEN
         PRINT 2000, INUM
         STOP
      ELSE
         SMACHR = RC( INUM )
      ENDIF
      RETURN
 2000 FORMAT( ' INUM =', I3, ' OUT OF RANGE IN SMACHR.',
     *        ' EXECUTION TERMINATED.' )
      END
C
C
C
      DOUBLE PRECISION FUNCTION DMACHR( INUM )
      INTEGER          INUM
      DOUBLE PRECISION RC( 5 )
C
C  REAL CONSTANTS (DOUBLE PRECISION).
C
C  NICK GOULD, JULY 1988.
C
C  RC(1) THE 'SMALLEST' POSITIVE NUMBER: 1 + RC(1) > 1.
C  RC(2) THE 'SMALLEST' POSITIVE NUMBER: 1 - RC(2) < 1.
C  RC(3) THE SMALLEST NONZERO +VE REAL NUMBER.
C  RC(4) THE SMALLEST FULL PRECISION +VE REAL NUMBER.
C  RC(5) THE LARGEST FINITE +VE REAL NUMBER.
C
      DATA RC( 1 ) / 2.2204460492503132D-16 /
      DATA RC( 2 ) / 1.1102230246251566D-16 /
      DATA RC( 3 ) / 2.225073858507202D-308 /
      DATA RC( 4 ) / 2.225073858507202D-308 /
      DATA RC( 5 ) / 1.797693134862314D+308 /
      IF ( INUM .LE. 0 .OR. INUM .GE. 6 ) THEN
         PRINT 2000, INUM
         STOP
      ELSE
         DMACHR = RC( INUM )
      ENDIF
      RETURN
 2000 FORMAT( ' INUM =', I3, ' OUT OF RANGE IN DMACHR.',
     *        ' EXECUTION TERMINATED.' )
      END
C
      REAL FUNCTION CPUTIM( DUM )
C
C  GIVES THE CPU TIME IN SECONDS.
C
C  THE REMAINING LINES SHOULD BE REPLACED BY A DEFINITION AND CALL
C  TO THE SYSTEM DEPENDENT CPU TIMING ROUTINE.
C
      REAL             ETIME, DUMMY( 2 )
C
C  OBTAIN THE CPU TIME.
C
      CPUTIM = ETIME( DUMMY )
      RETURN
C
C  END OF CPUTIM.
C
      END
