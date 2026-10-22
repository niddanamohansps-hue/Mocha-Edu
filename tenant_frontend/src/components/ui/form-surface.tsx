import * as React from "react"

/**
 * True inside dialogs and side panels, where nearly every control is a form field and should fill
 * the width of its field instead of shrinking to the width of its text.
 */
export const FormSurfaceContext = React.createContext(false)
