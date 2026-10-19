Add-Type -AssemblyName System.Drawing
function DrawNode($g,$x,$y,$w,$h,$label) {
    $rect = New-Object System.Drawing.Rectangle($x,$y,$w,$h)
    $fill = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(232,245,244))
    $pen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(62,125,145),2)
    $font = New-Object System.Drawing.Font('Arial',12,[System.Drawing.FontStyle]::Bold)
    $sf = New-Object System.Drawing.StringFormat
    $sf.Alignment = [System.Drawing.StringAlignment]::Center
    $sf.LineAlignment = [System.Drawing.StringAlignment]::Center
    $g.FillRectangle($fill,$rect)
    $g.DrawRectangle($pen,$rect)
    $g.DrawString($label,$font,[System.Drawing.Brushes]::MidnightBlue,[System.Drawing.RectangleF]$rect,$sf)
}
function DrawArrow($g,$x1,$y1,$x2,$y2,$label) {
    $pen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(62,125,145),2)
    $pen.EndCap = [System.Drawing2D.LineCap]::ArrowAnchor
    $g.DrawLine($pen,$x1,$y1,$x2,$y2)
    $font = New-Object System.Drawing.Font('Arial',8)
    $g.DrawString($label,$font,[System.Drawing.Brushes]::DimGray,[single](($x1+$x2)/2-35),[single](($y1+$y2)/2-14))
}
function NewCanvas($title) {
    $script:bmp = New-Object System.Drawing.Bitmap(1320,470)
    $script:g = [System.Drawing.Graphics]::FromImage($script:bmp)
    $script:g.SmoothingMode = [System.Drawing2D.SmoothingMode]::AntiAlias
    $script:g.Clear([System.Drawing.Color]::White)
    $font = New-Object System.Drawing.Font('Arial',16,[System.Drawing.FontStyle]::Bold)
    $script:g.DrawString($title,$font,[System.Drawing.Brushes]::MidnightBlue,30,10)
}
function SaveCanvas($name) {
    $script:bmp.Save((Join-Path (Get-Location) $name),[System.Drawing.Imaging.ImageFormat]::Png)
    $script:g.Dispose()
    $script:bmp.Dispose()
}
NewCanvas 'EDU Sekai â€” System Architecture'
DrawNode $g 30 100 220 60 'Public SaaS Site'; DrawNode $g 30 250 220 60 'Tenant Dashboard'; DrawNode $g 350 165 240 70 'Django Tenant Middleware'; DrawNode $g 690 90 230 65 'Auth + Tenant RBAC'; DrawNode $g 690 225 230 65 'Django REST APIs'; DrawNode $g 1050 70 230 70 'Public Schema'; DrawNode $g 1050 190 230 80 'Tenant Schema per School'; DrawNode $g 690 360 230 60 'Redis / Celery'; DrawNode $g 1050 360 230 60 'Email / SMTP'
DrawArrow $g 250 130 350 185 'signup/auth'; DrawArrow $g 250 280 350 215 'tenant host'; DrawArrow $g 590 195 690 120 'tenant context'; DrawArrow $g 805 155 805 225 'authorized requests'; DrawArrow $g 920 245 1050 105 'identity/signup'; DrawArrow $g 920 250 1050 230 'school data'; DrawArrow $g 805 290 805 360 'tasks'; DrawArrow $g 920 390 1050 390 'email delivery'; SaveCanvas 'architecture-diagram.png'
NewCanvas 'Core School Workflow'
DrawNode $g 35 170 190 70 'School Setup'; DrawNode $g 300 65 220 75 'Academic Structure'; DrawNode $g 300 175 220 75 'Staff / Instructors'; DrawNode $g 300 290 220 75 'Families / Guardians'; DrawNode $g 610 170 220 75 'Student Enrollment'; DrawNode $g 920 50 180 65 'Timetable'; DrawNode $g 920 135 180 65 'Attendance'; DrawNode $g 920 220 180 65 'LMS / Assignments'; DrawNode $g 920 305 180 65 'Exams / Results'; DrawNode $g 920 390 180 60 'Fees / Payments'; DrawNode $g 1160 190 150 85 'Parent Portal'
DrawArrow $g 225 205 300 100 'configure'; DrawArrow $g 225 205 300 210 'onboard'; DrawArrow $g 225 205 300 325 'link'; DrawArrow $g 520 100 610 195 'levels/sections'; DrawArrow $g 520 210 610 205 'staff'; DrawArrow $g 520 325 610 225 'relations'; DrawArrow $g 830 200 920 85 'schedule'; DrawArrow $g 830 200 920 165 'mark'; DrawArrow $g 830 200 920 250 'content'; DrawArrow $g 830 200 920 335 'assess'; DrawArrow $g 830 200 920 420 'charge'; DrawArrow $g 1100 165 1160 220 'attendance'; DrawArrow $g 1100 250 1160 225 'results'; DrawArrow $g 1100 420 1160 250 'fees'; SaveCanvas 'school-workflow-diagram.png'
NewCanvas 'Proposed Admissions Applicant Workflow'
DrawNode $g 35 190 190 70 'Enquiry'; DrawNode $g 300 190 190 70 'Application'; DrawNode $g 565 190 190 70 'Documents'; DrawNode $g 830 190 190 70 'Review / Decision'; DrawNode $g 1090 190 190 70 'Convert to Student'; DrawArrow $g 225 225 300 225 'apply'; DrawArrow $g 490 225 565 225 'submit'; DrawArrow $g 755 225 830 225 'verify'; DrawArrow $g 1020 225 1090 225 'accept'; SaveCanvas 'admissions-diagram.png'
NewCanvas 'Proposed Staff Leave Workflow'
DrawNode $g 50 190 210 70 'Leave Request'; DrawNode $g 360 190 210 70 'Manager Approval'; DrawNode $g 670 190 210 70 'Balance / Calendar'; DrawNode $g 980 190 250 70 'Attendance Reconciliation'; DrawArrow $g 260 225 360 225 'submit'; DrawArrow $g 570 225 670 225 'approve'; DrawArrow $g 880 225 980 225 'approved dates'; SaveCanvas 'leave-diagram.png'
NewCanvas 'Proposed Student Fee Online Payment'
DrawNode $g 40 190 190 70 'Fee / Installment'; DrawNode $g 300 190 190 70 'Payment Initiation'; DrawNode $g 560 190 190 70 'Payment Gateway'; DrawNode $g 820 190 190 70 'Verify Callback'; DrawNode $g 1080 190 190 70 'Allocate / Receipt'; DrawArrow $g 230 225 300 225 'due'; DrawArrow $g 490 225 560 225 'pay'; DrawArrow $g 750 225 820 225 'signed result'; DrawArrow $g 1010 225 1080 225 'verified'; SaveCanvas 'online-fees-diagram.png'
NewCanvas 'Proposed Student Transfer and Certificate Workflow'
DrawNode $g 35 190 200 70 'Transfer Request'; DrawNode $g 300 190 200 70 'Approval'; DrawNode $g 565 190 200 70 'Clearances'; DrawNode $g 830 190 200 70 'Lifecycle Record'; DrawNode $g 1090 190 200 70 'Issue Certificate'; DrawArrow $g 235 225 300 225 'review'; DrawArrow $g 500 225 565 225 'approved'; DrawArrow $g 765 225 830 225 'complete'; DrawArrow $g 1030 225 1090 225 'generate'; SaveCanvas 'certificates-diagram.png'
NewCanvas 'Proposed Library and Transport Workflows'
DrawNode $g 40 85 210 70 'Book Catalogue'; DrawNode $g 350 85 210 70 'Issue / Return'; DrawNode $g 660 85 210 70 'Due / Renewal'; DrawNode $g 970 85 210 70 'Fine â†’ Fees'; DrawArrow $g 250 120 350 120 'select'; DrawArrow $g 560 120 660 120 'loan'; DrawArrow $g 870 120 970 120 'overdue'; DrawNode $g 40 300 210 70 'Vehicles / Routes'; DrawNode $g 350 300 210 70 'Stops / Drivers'; DrawNode $g 660 300 210 70 'Student Assignment'; DrawNode $g 970 300 210 70 'Route Fee'; DrawArrow $g 250 335 350 335 'configure'; DrawArrow $g 560 335 660 335 'assign'; DrawArrow $g 870 335 970 335 'bill'; SaveCanvas 'library-transport-diagram.png'
NewCanvas 'Proposed Health, Calendar, LMS and Inventory'
DrawNode $g 30 100 250 75 'Health: profile / allergies'; DrawNode $g 360 100 250 75 'Incident / emergency contact'; DrawNode $g 690 100 250 75 'Calendar / school events'; DrawNode $g 1020 100 250 75 'Timetable / notices'; DrawArrow $g 280 138 360 138 'record'; DrawArrow $g 940 138 1020 138 'inform'; DrawNode $g 30 290 250 75 'Ordered Lessons'; DrawNode $g 360 290 250 75 'Quizzes'; DrawNode $g 690 290 250 75 'Progress Tracking'; DrawNode $g 1020 290 250 75 'Teacher Reports'; DrawArrow $g 280 328 360 328 'assess'; DrawArrow $g 610 328 690 328 'measure'; DrawArrow $g 940 328 1020 328 'review'; SaveCanvas 'other-modules-diagram.png'
NewCanvas 'Suggested Module Dependency Roadmap'
DrawNode $g 35 190 210 75 'Platform + Year'; DrawNode $g 300 190 210 75 'Admissions'; DrawNode $g 565 190 210 75 'Student Lifecycle'; DrawNode $g 830 70 210 75 'Leave / HR'; DrawNode $g 830 190 210 75 'Core School Ops'; DrawNode $g 830 310 210 75 'Fees / Documents'; DrawNode $g 1090 190 210 75 'Library / Transport / BI'; DrawArrow $g 245 228 300 228 'foundation'; DrawArrow $g 510 228 565 228 'intake'; DrawArrow $g 775 210 830 108 'staff'; DrawArrow $g 775 228 830 228 'enrollment'; DrawArrow $g 775 245 830 348 'student records'; DrawArrow $g 1040 228 1090 228 'expand'; SaveCanvas 'roadmap-diagram.png'
Write-Output "Rendered diagrams"
Get-ChildItem '*-diagram.png' | Select-Object Name,Length
