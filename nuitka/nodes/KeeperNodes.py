#     Copyright 2012, Kay Hayen, mailto:kayhayen@gmx.de
#
#     Part of "Nuitka", an optimizing Python compiler that is compatible and
#     integrates with CPython, but also works on its own.
#
#     If you submit patches or make the software available to licensors of
#     this software in either form, you automatically them grant them a
#     license for your part of the code under "Apache License 2.0" unless you
#     choose to remove this notice.
#
#     Kay Hayen uses the right to license his code under only GPL version 3,
#     to discourage a fork of Nuitka before it is "finished". He will later
#     make a new "Nuitka" release fully under "Apache License 2.0".
#
#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, version 3 of the License.
#
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#     Please leave the whole of this copyright notice intact.
#
""" Keeper nodes.

We need keeper nodes for comparison chains to hold the previous value during the
evaluation of an expression. They are otherwise not used and should be avoided,
all other constructs use real temporary variables.

"""

from .NodeBases import (
    CPythonExpressionChildrenHavingBase,
    CPythonExpressionMixin,
    CPythonNodeBase
)


class CPythonExpressionAssignmentTempKeeper( CPythonExpressionChildrenHavingBase ):
    kind = "EXPRESSION_ASSIGNMENT_TEMP_KEEPER"

    named_children = ( "source", )

    def __init__( self, variable_name, source, source_ref ):
        CPythonExpressionChildrenHavingBase.__init__(
            self,
            values     = {
                "source" : source,
            },
            source_ref = source_ref
        )

        self.variable_name = variable_name

    def getDetail( self ):
        return "%s from %s" % ( self.getVariableName(), self.getAssignSource() )

    def getVariableName( self ):
        return self.variable_name

    getAssignSource = CPythonExpressionChildrenHavingBase.childGetter( "source" )

    def computeNode( self ):
        # TODO: Nothing to do here? Maybe if the assignment target is unused, it could
        # replace itself with source.
        return self, None, None


class CPythonExpressionTempKeeperRef( CPythonNodeBase, CPythonExpressionMixin ):
    kind = "EXPRESSION_TEMP_KEEPER_REF"

    def __init__( self, linked, source_ref ):
        CPythonNodeBase.__init__( self, source_ref = source_ref )

        self.linked = linked

    def getDetails( self ):
        return { "name" : self.getVariableName() }

    def getDetail( self ):
        return self.getVariableName()

    def getVariableName( self ):
        return self.linked.getVariableName()

    def getLinkedKeeperAssignment( self ):
        return self.linked

    def computeNode( self ):
        # Nothing to do here.
        return self, None, None

    def mayRaiseException( self, exception_type ):
        # Can't happen
        return False