Sub CalculPortance()
'Calcul de la pression admissible. Tient compte de la méthode de calcul choisie et du coefficient de sécurité.
'Les largeurs de semelles sont de 60 et 150 centimètres si l'utilisateur n'a pas défini d'autres valeurs.
    On Error GoTo erreur
    
    Dim Cellules As Range
    Dim ligne As Range
    Dim pressionAdmissible1 As Double
    Dim pressionAdmissible2 As Double
    Dim profondeurCellule As Double
    Dim q As Double
    Dim phip As Double
    Dim rapportOk As Boolean
    Dim i As Integer
    Dim j As Integer
    Dim phiu As Double
    
    Dim qp As Double
    
    rapportOk = False
    i = CPTVariables.numeroPremiereLigneARemplir
    j = 1
    
    If Not VerifierFeuilleResultats Then
        MsgBox "Valeurs d'angles de frottement non disponibles. Lancez d'abord ce calcul.", vbInformation
        Exit Sub
    End If

    VerifierGamma
    DefinirZoneDonnees
    VerifierMethode
    rapportOk = VerifierRapport
    
    Set Cellules = CPTVariables.ZoneDonnees
    Set CPTVariables.tableauResultats = Sheets("Résultats essai CPT").Range("A3:J" & CStr(2 + Cellules.Rows.Count))
    
    On Error Resume Next
    For Each ligne In Cellules.Rows
        phiu = DegreToRadian(CPTVariables.tableauResultats.Cells(j, 7).Value) 'Récupère la valeur de l'angle phiu dans le tableau de résultats
        phip = DegreToRadian(CPTVariables.tableauResultats.Cells(j, 6).Value)
        profondeurCellule = ligne.Cells(1, 1).Value
        q = contrainte(profondeurCellule)
        qp = q
        'La méthode de DE BEER permet de tenir compte d'une différence de niveau des terrains après travaux. Cela requiert l'emploi d'une autre valeur de la contrainte naturelle, qp.
        'Ici cette possibilité n'est pas utilisée car jugée non pertinente, on prend donc q = qp (car les formules implémentées demandent le paramètre qp)
        Select Case CPTVariables.methodePression 'Choix de la bonne formule suivant la méthode demandée.
        Case "BrinchHansen"
            pressionAdmissible1 = BrinchHansen(phiu, 0, q, CSng(CPTVariables.largeurSemelle1 / 100), profondeurCellule)
            pressionAdmissible2 = BrinchHansen(phiu, 0, q, CSng(CPTVariables.largeurSemelle2 / 100), profondeurCellule)
        Case "CaquotKerisel"
            pressionAdmissible1 = CaquotKerisel(phiu, 0, q, CSng(CPTVariables.largeurSemelle1 / 100), profondeurCellule)
            pressionAdmissible2 = CaquotKerisel(phiu, 0, q, CSng(CPTVariables.largeurSemelle2 / 100), profondeurCellule)
        Case "Meyerhof"
            pressionAdmissible1 = Meyerhof(phiu, 0, q, CSng(CPTVariables.largeurSemelle1 / 100), profondeurCellule)
            pressionAdmissible2 = Meyerhof(phiu, 0, q, CSng(CPTVariables.largeurSemelle2 / 100), profondeurCellule)
        Case "INISMa"
            pressionAdmissible1 = PressionInisma(profondeurCellule, phip, phiu, qp, q, CSng(CPTVariables.largeurSemelle1 / 100), i)
            pressionAdmissible2 = PressionInisma(profondeurCellule, phip, phiu, qp, q, CSng(CPTVariables.largeurSemelle2 / 100), i)
        End Select
    pressionAdmissible1 = (pressionAdmissible1 / CPTVariables.CoefficientSecurite) * (10 / (10000 * g)) ' passe de DaN/m² à kg/cm²
    pressionAdmissible2 = pressionAdmissible2 / CPTVariables.CoefficientSecurite * (10 / (10000 * g))
    
        'ajout pour régler le problème des 0
    If pressionAdmissible1 < 0.1 Then
        pressionAdmissible1 = (CPTVariables.tableauResultats.Cells(j, 3).Value) / 10
    End If
    If pressionAdmissible2 < 0.1 Then
        pressionAdmissible2 = pressionAdmissible1
    End If
    
    CPTVariables.tableauResultats.Cells(j, 8).Value = pressionAdmissible1 'Enregistrement dans le tableau de valeurs
    CPTVariables.tableauResultats.Cells(j, 9).Value = pressionAdmissible2
    If rapportOk And (i < CPTVariables.numeroPremiereLigneARemplir + 50) Then
        Sheets("Rapport").Range(CStr("I" & i)).Value = pressionAdmissible1 'Remplissage des colonnes de la feuille Rapport
        Sheets("Rapport").Range(CStr("J" & i)).Value = pressionAdmissible2
    End If
    i = i + 1
    j = j + 1
    Next
Set Cellules = Nothing

Exit Sub
erreur:
    MsgBox "Une erreur est survenue lors du calcul de la pression admissible.", vbCritical
    Set Cellules = Nothing
End Sub


Private Function PressionInisma(Profondeur As Double, phip As Double, phiu As Double, qp As Double, q0p As Double, b1 As Single, i As Integer) As Double
'Calcul de la pression admissible selon la méthode de DE BEER (cf. Sanglerat)
    Dim terme1 As Double
    Dim terme2 As Double
    Dim terme3 As Double
    Dim terme4 As Double
    Dim terme5 As Double
    Dim Nq As Double
    Dim gamma As Double
    Dim rapportOk As Boolean
    
    rapportOk = VerifierRapport
    
    If CPTVariables.eauChantierSet And Profondeur > CPTVariables.niveauEauFinChantier Then
        gamma = (CPTVariables.masseVolumiqueSat - 1000) * (g / 10)
    Else
        gamma = CPTVariables.masseVolumiqueSec * (g / 10)
    End If
    
    If phiu < 0.001 Then GoTo fin
    terme1 = FPhipPhiu(phiu, phip)
    Nq = (terme1 * Tan(phip) * ((qp / q0p) ^ (Tan(phiu) / Tan(phip))) - (Tan(phip) / Tan(phiu)) + 1)
    terme2 = q0p * Nq
    terme3 = Vpg(phiu)
    terme4 = terme3 * gamma * b1
    'vpc = 0 'N'intervient pas
    'terme5 = vpc * cp
fin:
    Sheets("Résultats essai CPT").Range(CStr("K" & (3 + i - CPTVariables.numeroPremiereLigneARemplir))).Value = Nq
    Sheets("Résultats essai CPT").Range(CStr("L" & (3 + i - CPTVariables.numeroPremiereLigneARemplir))).Value = terme3
    If rapportOk And (i < CPTVariables.numeroPremiereLigneARemplir + 50) Then
        Sheets("Rapport").Range(CStr("G" & i)).Value = Nq
        Sheets("Rapport").Range(CStr("H" & i)).Value = terme3
    End If
    
    PressionInisma = (terme2 + terme4 + terme5)
End Function

Public Function Vpg(phiu As Double) As Double
'Vpg de la méthode de DE BEER
    Dim terme1 As Double
    Dim terme2 As Double
    Dim terme3 As Double
    Dim terme4 As Double
    Dim terme5 As Double

    terme1 = (1 + (Tan((pi / 4) + (phiu / 2))) ^ 2) / (1 + 9 * ((Tan(phiu)) ^ 2))
    terme2 = (3 * (Tan(phiu) * Tan((pi / 4) + (phiu / 2))) - 1) * Exp((3 / 2) * pi * Tan(phiu))
    terme3 = 3 * Tan(phiu) + Tan((pi / 4) + (phiu / 2))
    terme4 = 2 * Exp((3 / 2) * pi * Tan(phiu)) * ((Tan((pi / 4) + (phiu / 2))) ^ 2)
    terme5 = -2 * Tan((pi / 4) + (phiu / 2))
    
    Vpg = (1 / 8) * (terme1 * (terme2 + terme3) + terme4 + terme5)

End Function
Private Function Terzaghi(phi As Double, c As Double, q As Double, b As Single, prof As Double) As Double
'Calcul de la pression admissible selon Terzaghi
    Dim Nq As Double
    'Dim Nc As Double
    Dim Ng As Double
    Dim Kpg As Double 'Kp gamma donné par des tables!!!!!
    
    Nq = Exp(((3 * pi / 2) + phi) * Tan(phi)) / (2 * (Cos((pi / 4) + (phi / 2)) ^ 2))
    Nc = (Nq - 1) * ((Cos(phi)) / (Sin(phi)))
    Ng = 0.5 * Tan(phi) * ((Kpg / (Cos(phi) ^ 2)) - 1)
    
    If prof < CPTVariables.niveauEauFinChantier Then
        Terzaghi = q * Nq + CPTVariables.masseVolumiqueSec * (g / 10) * (b / 2) * Ng
    Else
        Terzaghi = q * Nq + CPTVariables.masseVolumiqueSat * (g / 10) * (b / 2) * Ng
    End If
End Function
Private Function BrinchHansen(phi As Double, c As Double, q As Double, b As Single, prof As Double) As Double
'Calcul de la pression admissible selon les formules de Brinch-Hansen
    Dim Nq As Double
    'Dim Nc As Double
    Dim Ng As Double
    
    Nq = Exp(pi * Tan(phi)) * (Tan((pi / 4) + (phi / 2)) ^ 2)
    'Nc = (Nq - 1) * ((Cos(phi)) / (Sin(phi)))
    Ng = 1.5 * (Nq - 1) * Tan(phi)
    
    If prof < CPTVariables.niveauEauFinChantier Then
        BrinchHansen = q * Nq + CPTVariables.masseVolumiqueSec * (g / 10) * (b) * Ng
    Else
        BrinchHansen = q * Nq + CPTVariables.masseVolumiqueSat * (g / 10) * (b) * Ng
    End If
End Function
Private Function CaquotKerisel(phi As Double, c As Double, q As Double, b As Single, prof As Double) As Double
'Calcul de la pression admissible selon les formules de Caquot et Kérisel
    Dim Nq As Double
    Dim Ng As Double
    Dim Kp As Double
    
    Kp = Tan((pi / 4) + (phi / 2)) ^ 2
    Nq = Exp(pi * Tan(phi)) * (Tan((pi / 4) + (phi / 2)) ^ 2)
    Ng = ((Cos((pi / 4) - (phi / 2))) / (2 * Sin((pi / 4) + (phi / 2)) ^ 2)) * (Kp - Sin((pi / 4) - (phi / 2)))
    If prof < CPTVariables.niveauEauFinChantier Then
        CaquotKerisel = q * Nq + CPTVariables.masseVolumiqueSec * (g / 10) * b * Ng
    Else
        CaquotKerisel = q * Nq + CPTVariables.masseVolumiqueSat * (g / 10) * b * Ng
    End If
End Function
Private Function Meyerhof(phi As Double, c As Double, q As Double, b As Single, prof As Double) As Double
'Calcul de la pression admissible selon les formules de Meyerhof
    Dim Nq As Double
    Dim Ng As Double
    
    Nq = Exp(pi * Tan(phi)) * (Tan((pi / 4) + (phi / 2)) ^ 2)
    Ng = (Nq - 1) * Tan(1.4 * phi)
    If prof < CPTVariables.niveauEauFinChantier Then
        Meyerhof = q * Nq + CPTVariables.masseVolumiqueSec * (g / 10) * b * Ng
    Else
        Meyerhof = q * Nq + CPTVariables.masseVolumiqueSat * (g / 10) * b * Ng
    End If
End Function


