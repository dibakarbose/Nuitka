#     Copyright 2018, Kay Hayen, mailto:kay.hayen@gmail.com
#
#     Part of "Nuitka", an optimizing Python compiler that is compatible and
#     integrates with CPython, but also works on its own.
#
#     Licensed under the Apache License, Version 2.0 (the "License");
#     you may not use this file except in compliance with the License.
#     You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#     Unless required by applicable law or agreed to in writing, software
#     distributed under the License is distributed on an "AS IS" BASIS,
#     WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#     See the License for the specific language governing permissions and
#     limitations under the License.
#
""" Reformulation of Python3 class statements.

Consult the developer manual for information. TODO: Add ability to sync
source code comments with developer manual sections.

"""

from nuitka.nodes.AssignNodes import (
    StatementAssignmentVariable,
    StatementAssignmentVariableName,
    StatementReleaseVariable
)
from nuitka.nodes.AttributeNodes import (
    ExpressionAttributeLookup,
    ExpressionBuiltinHasattr
)
from nuitka.nodes.BuiltinRefNodes import makeExpressionBuiltinRef
from nuitka.nodes.CallNodes import makeExpressionCall
from nuitka.nodes.ClassNodes import (
    ExpressionClassBody,
    ExpressionSelectMetaclass
)
from nuitka.nodes.CodeObjectSpecs import CodeObjectSpec
from nuitka.nodes.ConditionalNodes import (
    ExpressionConditional,
    makeStatementConditional
)
from nuitka.nodes.ConstantRefNodes import makeConstantRefNode
from nuitka.nodes.ContainerMakingNodes import ExpressionMakeTuple
from nuitka.nodes.DictionaryNodes import (
    ExpressionDictOperationGet,
    ExpressionDictOperationIn,
    StatementDictOperationRemove,
    StatementDictOperationUpdate
)
from nuitka.nodes.FunctionNodes import ExpressionFunctionQualnameRef
from nuitka.nodes.GlobalsLocalsNodes import ExpressionBuiltinLocalsRef
from nuitka.nodes.LocalsDictNodes import (
    StatementLocalsDictOperationSet,
    StatementReleaseLocals,
    StatementSetLocals
)
from nuitka.nodes.NodeMakingHelpers import mergeStatements
from nuitka.nodes.ReturnNodes import StatementReturn
from nuitka.nodes.SubscriptNodes import ExpressionSubscriptLookup
from nuitka.nodes.TypeNodes import ExpressionBuiltinType1
from nuitka.nodes.VariableRefNodes import (
    ExpressionTempVariableRef,
    ExpressionVariableRef
)
from nuitka.PythonVersions import python_version

from .ReformulationSequenceCreation import buildTupleCreationNode
from .ReformulationTryFinallyStatements import makeTryFinallyStatement
from .TreeHelpers import (
    buildFrameNode,
    buildNode,
    buildNodeList,
    extractDocFromBody,
    makeDictCreationOrConstant2,
    makeSequenceCreationOrConstant,
    makeStatementsSequenceFromStatement,
    mangleName
)


def buildClassNode3(provider, node, source_ref):
    # Many variables, due to the huge re-formulation that is going on here,
    # which just has the complexity and optimization checks:
    # pylint: disable=too-many-branches,too-many-locals,too-many-statements,I0021

    # This function is the Python3 special case with special re-formulation as
    # according to developer manual.
    class_statement_nodes, class_doc = extractDocFromBody(node)

    # We need a scope for the temporary variables, and they might be closured.
    temp_scope = provider.allocateTempScope(
        name = "class_creation"
    )

    tmp_class_decl_dict = provider.allocateTempVariable(
        temp_scope = temp_scope,
        name       = "class_decl_dict"
    )
    tmp_metaclass = provider.allocateTempVariable(
        temp_scope = temp_scope,
        name       = "metaclass"
    )
    tmp_prepared = provider.allocateTempVariable(
        temp_scope = temp_scope,
        name       = "prepared"
    )

    class_creation_function = ExpressionClassBody(
        provider   = provider,
        name       = node.name,
        doc        = class_doc,
        source_ref = source_ref
    )

    class_variable = class_creation_function.getVariableForAssignment(
        "__class__"
    )

    class_variable_ref = ExpressionVariableRef(
        variable   = class_variable,
        source_ref = source_ref
    )

    parent_module = provider.getParentModule()

    code_object = CodeObjectSpec(
        co_name           = node.name,
        co_kind           = "Class",
        co_varnames       = (),
        co_argcount       = 0,
        co_kwonlyargcount = 0,
        co_has_starlist   = False,
        co_has_stardict   = False,
        co_filename       = parent_module.getRunTimeFilename(),
        co_lineno         = source_ref.getLineNumber(),
        future_spec       = parent_module.getFutureSpec()
    )

    body = buildFrameNode(
        provider    = class_creation_function,
        nodes       = class_statement_nodes,
        code_object = code_object,
        source_ref  = source_ref
    )

    source_ref_orig = source_ref

    if body is not None:
        # The frame guard has nothing to tell its line number to.
        body.source_ref = source_ref

    statements = [
        StatementSetLocals(
            locals_scope = class_creation_function.getLocalsScope(),
            new_locals   = ExpressionTempVariableRef(
                variable   = tmp_prepared,
                source_ref = source_ref
            ),
            source_ref   = source_ref
        ),
        StatementAssignmentVariableName(
            provider      = class_creation_function,
            variable_name = "__module__",
            source        = makeConstantRefNode(
                constant      = provider.getParentModule().getFullName(),
                source_ref    = source_ref,
                user_provided = True
            ),
            source_ref    = source_ref
        )
    ]

    if class_doc is not None:
        statements.append(
            StatementAssignmentVariableName(
                provider      = class_creation_function,
                variable_name = "__doc__",
                source        = makeConstantRefNode(
                    constant      = class_doc,
                    source_ref    = source_ref,
                    user_provided = True
                ),
                source_ref    = source_ref
            )
        )

    # The "__qualname__" attribute is new in Python 3.3.
    if python_version >= 300:
        qualname = class_creation_function.getFunctionQualname()

        if python_version < 340:
            qualname_ref = makeConstantRefNode(
                constant      = qualname,
                source_ref    = source_ref,
                user_provided = True
            )
        else:
            qualname_ref = ExpressionFunctionQualnameRef(
                function_body = class_creation_function,
                source_ref    = source_ref,
            )

        statements.append(
            StatementLocalsDictOperationSet(
                locals_scope  = class_creation_function.getLocalsScope(),
                variable_name = "__qualname__",
                value         = qualname_ref,
                source_ref    = source_ref
            )
        )

        if python_version >= 340:
            qualname_assign = statements[-1]

    if python_version >= 360 and \
       class_creation_function.needsAnnotationsDictionary():
        statements.append(
            StatementLocalsDictOperationSet(
                locals_scope  = class_creation_function.getLocalsScope(),
                variable_name = "__annotations__",
                value         = makeConstantRefNode(
                    constant      = {},
                    source_ref    = source_ref,
                    user_provided = True
                ),
                source_ref    = source_ref
            )
        )

    statements.append(body)

    if node.bases:
        tmp_bases = provider.allocateTempVariable(
            temp_scope = temp_scope,
            name       = "bases"
        )

        def makeBasesRef():
            return ExpressionTempVariableRef(
                variable   = tmp_bases,
                source_ref = source_ref
            )
    else:
        def makeBasesRef():
            return makeConstantRefNode(
                constant   = (),
                source_ref = source_ref
            )

    statements += [
        StatementAssignmentVariable(
            variable   = class_variable,
            source     = makeExpressionCall(
                called     = ExpressionTempVariableRef(
                    variable   = tmp_metaclass,
                    source_ref = source_ref
                ),
                args       = makeSequenceCreationOrConstant(
                    sequence_kind = "tuple",
                    elements      = (
                        makeConstantRefNode(
                            constant      = node.name,
                            source_ref    = source_ref,
                            user_provided = True
                        ),
                        makeBasesRef(),
                        ExpressionBuiltinLocalsRef(
                            locals_scope = class_creation_function.getLocalsScope(),
                            source_ref   = source_ref
                        )
                    ),
                    source_ref    = source_ref
                ),
                kw         = ExpressionTempVariableRef(
                    variable   = tmp_class_decl_dict,
                    source_ref = source_ref
                ),
                source_ref = source_ref
            ),
            source_ref = source_ref
        ),
        StatementReturn(
            expression = class_variable_ref,
            source_ref = source_ref
        )
    ]

    body = makeStatementsSequenceFromStatement(
        statement = makeTryFinallyStatement(
            provider   = class_creation_function,
            tried      = mergeStatements(statements, True),
            final      = StatementReleaseLocals(
                locals_scope = class_creation_function.getLocalsScope(),
                source_ref   = source_ref
            ),
            source_ref = source_ref
        )
    )

    # The class body is basically a function that implicitly, at the end
    # returns its locals and cannot have other return statements contained.
    class_creation_function.setBody(body)

    # The class body is basically a function that implicitly, at the end
    # returns its created class and cannot have other return statements
    # contained.

    decorated_body = class_creation_function

    for decorator in buildNodeList(
            provider,
            reversed(node.decorator_list),
            source_ref
        ):
        decorated_body = makeExpressionCall(
            called     = decorator,
            args       = ExpressionMakeTuple(
                elements   = (
                    decorated_body,
                ),
                source_ref = source_ref
            ),
            kw         = None,
            source_ref = decorator.getSourceReference()
        )

    if node.keywords and node.keywords[-1].arg is None:
        keywords = node.keywords[:-1]
    else:
        keywords = node.keywords

    statements = []

    if node.bases:
        statements.append(
            StatementAssignmentVariable(
                variable   = tmp_bases,
                source     = buildTupleCreationNode(
                    provider   = provider,
                    elements   = node.bases,
                    source_ref = source_ref
                ),
                source_ref = source_ref
            )
        )

    statements.append(
        StatementAssignmentVariable(
            variable   = tmp_class_decl_dict,
            source     = makeDictCreationOrConstant2(
                keys       = [
                    keyword.arg
                    for keyword in
                    keywords
                ],
                values     = [
                    buildNode(provider, keyword.value, source_ref)
                    for keyword in
                    keywords
                ],
                source_ref = source_ref
            ),
            source_ref = source_ref
        )
    )

    if node.keywords and node.keywords[-1].arg is None:
        statements.append(
            StatementDictOperationUpdate(
                dict_arg   = ExpressionVariableRef(
                    variable   = tmp_class_decl_dict,
                    source_ref = source_ref
                ),
                value      = buildNode(provider, node.keywords[-1].value, source_ref),
                source_ref = source_ref
            )
        )

    # Check if there are bases, and if there are, go with the type of the
    # first base class as a metaclass unless it was specified in the class
    # decl dict of course.
    if node.bases:
        unspecified_metaclass_expression = ExpressionBuiltinType1(
            value      = ExpressionSubscriptLookup(
                subscribed = ExpressionTempVariableRef(
                    variable   = tmp_bases,
                    source_ref = source_ref
                ),
                subscript  = makeConstantRefNode(
                    constant      = 0,
                    source_ref    = source_ref,
                    user_provided = True
                ),
                source_ref = source_ref
            ),
            source_ref = source_ref
        )
    else:
        unspecified_metaclass_expression = makeExpressionBuiltinRef(
            builtin_name = "type",
            source_ref   = source_ref
        )

    statements += [
        StatementAssignmentVariable(
            variable   = tmp_metaclass,
            source     = ExpressionSelectMetaclass(
                metaclass  = ExpressionConditional(
                    condition      = ExpressionDictOperationIn(
                        key        = makeConstantRefNode(
                            constant      = "metaclass",
                            source_ref    = source_ref,
                            user_provided = True
                        ),
                        dict_arg   = ExpressionTempVariableRef(
                            variable   = tmp_class_decl_dict,
                            source_ref = source_ref
                        ),
                        source_ref = source_ref
                    ),
                    expression_yes = ExpressionDictOperationGet(
                        dict_arg   = ExpressionTempVariableRef(
                            variable   = tmp_class_decl_dict,
                            source_ref = source_ref
                        ),
                        key        = makeConstantRefNode(
                            constant      = "metaclass",
                            source_ref    = source_ref,
                            user_provided = True
                        ),
                        source_ref = source_ref
                    ),
                    expression_no  = unspecified_metaclass_expression,
                    source_ref     = source_ref
                ),
                bases      = makeBasesRef(),
                source_ref = source_ref
            ),
            source_ref = source_ref_orig
        ),
        makeStatementConditional(
            condition  = ExpressionDictOperationIn(
                key        = makeConstantRefNode(
                    constant      = "metaclass",
                    source_ref    = source_ref,
                    user_provided = True
                ),
                dict_arg   = ExpressionTempVariableRef(
                    variable   = tmp_class_decl_dict,
                    source_ref = source_ref
                ),
                source_ref = source_ref
            ),
            no_branch  = None,
            yes_branch = StatementDictOperationRemove(
                dict_arg   = ExpressionTempVariableRef(
                    variable   = tmp_class_decl_dict,
                    source_ref = source_ref
                ),
                key        = makeConstantRefNode(
                    constant      = "metaclass",
                    source_ref    = source_ref,
                    user_provided = True
                ),
                source_ref = source_ref
            ),
            source_ref = source_ref
        ),
        StatementAssignmentVariable(
            variable   = tmp_prepared,
            source     = ExpressionConditional(
                condition      = ExpressionBuiltinHasattr(
                    object_arg = ExpressionTempVariableRef(
                        variable   = tmp_metaclass,
                        source_ref = source_ref
                    ),
                    name       = makeConstantRefNode(
                        constant      = "__prepare__",
                        source_ref    = source_ref,
                        user_provided = True
                    ),
                    source_ref = source_ref
                ),
                expression_no  = makeConstantRefNode(
                    constant      = {},
                    source_ref    = source_ref,
                    user_provided = True
                ),
                expression_yes = makeExpressionCall(
                    called     = ExpressionAttributeLookup(
                        source         = ExpressionTempVariableRef(
                            variable   = tmp_metaclass,
                            source_ref = source_ref
                        ),
                        attribute_name = "__prepare__",
                        source_ref     = source_ref
                    ),
                    args       = ExpressionMakeTuple(
                        elements   = (
                            makeConstantRefNode(
                                constant      = node.name,
                                source_ref    = source_ref,
                                user_provided = True
                            ),
                            makeBasesRef(),
                        ),
                        source_ref = source_ref
                    ),
                    kw         = ExpressionTempVariableRef(
                        variable   = tmp_class_decl_dict,
                        source_ref = source_ref
                    ),
                    source_ref = source_ref
                ),
                source_ref     = source_ref
            ),
            source_ref = source_ref
        ),
        StatementAssignmentVariableName(
            provider      = provider,
            variable_name = mangleName(node.name, provider),
            source        = decorated_body,
            source_ref    = source_ref
        )
    ]

    if python_version >= 340:
        class_creation_function.qualname_setup = node.name, qualname_assign

    final = [tmp_class_decl_dict, tmp_metaclass, tmp_prepared]
    if node.bases:
        final.insert(0, tmp_bases)

    return makeTryFinallyStatement(
        provider   = provider,
        tried      = statements,
        final      = tuple(
            StatementReleaseVariable(
                variable = variable,
                source_ref = source_ref
            )
            for variable in
            final
        )
        ,
        source_ref = source_ref
    )
