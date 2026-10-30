# -*- coding: utf-8 -*-
"""Category-specific editorial content for the buy pages.

Four pages per municipality (land, houses, apartments, commercial) previously
differed mainly in their title and a handful of sentences, which is the shape
of a doorway cluster. The directory data has no per-category professional
specialisation to lean on, so the differentiation has to come from what
genuinely differs between these purchases: what you verify, what you ask, and
what you pay for.

Everything here is framed as something to check with a professional or a public
office rather than as an assertion about procedure or price, so no page claims
a fee, a deadline or a legal requirement that this project cannot source.
"""

# questions : asked of a professional, 4 per category
# checks    : (aspect, what to verify) rows, 5 per category
# costs     : (label, detail) items that make up the cost of this purchase
# costs_lead: one sentence introducing the cost list

ES = {
    "terrenos": {
        "questions": [
            "¿El lote tiene mensura actualizada y un plano que coincida con los linderos en el terreno?",
            "¿Qué uso de suelo tiene asignado y qué retiros o restricciones de construcción aplican?",
            "¿Hasta dónde llegan agua, energía y desagüe, y quién paga la extensión o la conexión?",
            "¿El acceso es por calle pública o depende de una servidumbre de paso inscripta?",
        ],
        "checks": [
            ("Matrícula y titularidad",
             "Pedí el número de finca o matrícula y comprobá en los Registros Públicos que quien vende sea el titular."),
            ("Mensura y linderos",
             "Compará el plano de mensura con las medidas reales del lote: una diferencia de superficie cambia el precio y la escritura."),
            ("Uso de suelo y retiros",
             "Consultá en la municipalidad la zonificación, el uso permitido y los retiros obligatorios antes de proyectar una construcción."),
            ("Servicios disponibles",
             "Verificá hasta qué punto llegan la red de agua, la energía eléctrica y el desagüe, y qué costo tiene conectarse."),
            ("Acceso y servidumbres",
             "Confirmá si el lote da a una calle pública o si el ingreso depende de una servidumbre constituida sobre otro inmueble."),
        ],
        "costs_lead": "Además del precio pedido, una compra de terreno suele involucrar estos conceptos. Pedí que te los detallen por escrito antes de señar.",
        "costs": [
            ("Escrituración y registro", "Honorarios de escribanía e inscripción de la transferencia."),
            ("Mensura o replanteo", "Actualización del plano y verificación de linderos en el terreno."),
            ("Conexión de servicios", "Extensión de red y derechos de conexión de agua y energía."),
            ("Preparación del suelo", "Limpieza, relleno o nivelación según la topografía del lote."),
            ("Impuesto inmobiliario", "Tributo municipal anual; pedí el certificado de deuda al día."),
        ],
    },
    "casas": {
        "questions": [
            "¿La construcción está declarada y coincide con lo que figura en catastro y en el registro?",
            "¿Qué antigüedad tiene la vivienda y cuándo se renovaron techo, instalación eléctrica y cañerías?",
            "¿Existen deudas de impuesto inmobiliario o de servicios asociadas al inmueble?",
            "¿Puedo hacer una inspección técnica independiente antes de firmar?",
        ],
        "checks": [
            ("Titularidad y gravámenes",
             "Pedí el informe de la finca para descartar hipotecas, embargos o litigios pendientes sobre el inmueble."),
            ("Construcción declarada",
             "Compará los metros construidos reales con los declarados: regularizar una ampliación no declarada suele quedar a cargo del comprador."),
            ("Estado de la construcción",
             "Revisá techo, humedades, instalación eléctrica y sanitaria; una inspección técnica independiente cuesta mucho menos que la reparación."),
            ("Deudas del inmueble",
             "Solicitá los certificados de impuesto inmobiliario y de servicios al día antes de firmar cualquier documento."),
            ("Barrio y accesos",
             "Visitá en distintos horarios y comprobá el estado de las calles, el desagüe pluvial y los servicios efectivamente disponibles."),
        ],
        "costs_lead": "Más allá del precio, estos son los conceptos que suelen aparecer al comprar una casa. Pedí un detalle por escrito.",
        "costs": [
            ("Escrituración y registro", "Honorarios de escribanía e inscripción de la transferencia."),
            ("Inspección técnica", "Revisión independiente de estructura, humedad e instalaciones."),
            ("Regularizaciones", "Declaración de ampliaciones o mejoras no registradas, si corresponde."),
            ("Reparaciones iniciales", "Trabajos detectados en la inspección antes de habitar la vivienda."),
            ("Impuesto inmobiliario", "Tributo municipal anual; verificá que no haya deuda acumulada."),
        ],
    },
    "departamentos": {
        "questions": [
            "¿Cuál es el valor actual de las expensas y qué servicios incluyen?",
            "¿Puedo revisar el reglamento de copropiedad y las últimas actas de asamblea?",
            "¿Hay obras aprobadas que generen una cuota extraordinaria en los próximos meses?",
            "¿Qué incluye exactamente la unidad: cochera, baulera y qué porcentaje de áreas comunes?",
        ],
        "checks": [
            ("Propiedad horizontal",
             "Comprobá que la unidad esté inscripta en régimen de propiedad horizontal y que tenga su propia matrícula."),
            ("Reglamento y expensas",
             "Pedí el reglamento de copropiedad, el monto de las expensas y el detalle de qué cubren y qué no."),
            ("Deudas de la unidad",
             "Solicitá un certificado de expensas al día: una deuda de la unidad suele seguir al inmueble, no al vendedor."),
            ("Obras y fondo de reserva",
             "Preguntá por obras aprobadas en asamblea, por el fondo de reserva y por cuotas extraordinarias previstas."),
            ("Superficie y accesorios",
             "Confirmá la superficie propia y la común, y si la cochera o la baulera son unidades independientes con matrícula aparte."),
        ],
        "costs_lead": "Comprar en un edificio suma gastos recurrentes al precio de la unidad. Conviene estimarlos antes de decidir.",
        "costs": [
            ("Expensas mensuales", "Gasto recurrente de administración, personal y mantenimiento."),
            ("Escrituración y registro", "Honorarios de escribanía e inscripción de la transferencia."),
            ("Fondo de reserva", "Aporte para reparaciones mayores del edificio."),
            ("Cuotas extraordinarias", "Obras aprobadas en asamblea que se cobran aparte de las expensas."),
            ("Impuesto inmobiliario", "Tributo municipal anual correspondiente a la unidad."),
        ],
    },
    "comerciales": {
        "questions": [
            "¿El uso de suelo y la habilitación municipal admiten la actividad que quiero desarrollar?",
            "¿Qué carga eléctrica disponible, superficie útil y acceso de carga tiene el local?",
            "¿Cómo es el flujo peatonal y vehicular del corredor y en qué horarios se concentra?",
            "¿Hay restricciones de cartelería, horarios de carga o estacionamiento en la zona?",
        ],
        "checks": [
            ("Uso de suelo y habilitación",
             "Confirmá en la municipalidad que la actividad prevista esté permitida en esa zona y qué requisitos exige la habilitación."),
            ("Aptitud del local",
             "Verificá carga eléctrica disponible, sanitarios, salidas de emergencia y superficie útil real frente a la publicada."),
            ("Acceso y logística",
             "Comprobá el acceso para carga y descarga, el estacionamiento y las restricciones de circulación del corredor."),
            ("Titularidad y gravámenes",
             "Pedí el informe registral de la finca y descartá hipotecas, embargos o litigios pendientes."),
            ("Entorno comercial",
             "Evaluá las actividades vecinas, el flujo del corredor y las obras previstas que puedan cambiar la circulación."),
        ],
        "costs_lead": "Un inmueble comercial se evalúa por lo que permite operar. Estos conceptos suelen integrar la inversión inicial.",
        "costs": [
            ("Escrituración y registro", "Honorarios de escribanía e inscripción de la transferencia."),
            ("Adecuación y habilitación", "Obras y trámites para cumplir los requisitos de la actividad."),
            ("Instalaciones y cartelería", "Carga eléctrica, climatización y señalización según normas locales."),
            ("Servicios con tarifa comercial", "Energía y agua suelen facturarse con tarifa distinta de la residencial."),
            ("Impuesto inmobiliario", "Tributo municipal anual; verificá que no haya deuda acumulada."),
        ],
    },
}

PT = {
    "terrenos": {
        "questions": [
            "O terreno tem levantamento atualizado e planta que coincida com as divisas no local?",
            "Qual uso do solo está atribuído ao lote e quais recuos ou restrições de construção se aplicam?",
            "Até onde chegam água, energia e esgoto, e quem paga a extensão ou a ligação?",
            "O acesso é por rua pública ou depende de uma servidão de passagem registrada?",
        ],
        "checks": [
            ("Matrícula e titularidade",
             "Peça o número da finca ou matrícula e confirme nos Registros Públicos que quem vende é o titular."),
            ("Medição e divisas",
             "Compare a planta de medição com as medidas reais do lote: uma diferença de área altera o preço e a escritura."),
            ("Uso do solo e recuos",
             "Consulte na prefeitura o zoneamento, o uso permitido e os recuos obrigatórios antes de projetar uma construção."),
            ("Serviços disponíveis",
             "Verifique até que ponto chegam a rede de água, a energia elétrica e o esgoto, e qual o custo de ligação."),
            ("Acesso e servidões",
             "Confirme se o lote dá para rua pública ou se a entrada depende de servidão constituída sobre outro imóvel."),
        ],
        "costs_lead": "Além do preço pedido, a compra de um terreno costuma envolver estes itens. Peça o detalhamento por escrito antes de sinalizar.",
        "costs": [
            ("Escritura e registro", "Honorários de tabelionato e registro da transferência."),
            ("Medição ou demarcação", "Atualização da planta e conferência das divisas no terreno."),
            ("Ligação de serviços", "Extensão de rede e direitos de ligação de água e energia."),
            ("Preparo do terreno", "Limpeza, aterro ou nivelamento conforme a topografia."),
            ("Imposto imobiliário", "Tributo municipal anual; peça a certidão de débitos."),
        ],
    },
    "casas": {
        "questions": [
            "A construção está declarada e corresponde ao que consta no cadastro e no registro?",
            "Qual a idade do imóvel e quando foram renovados telhado, instalação elétrica e tubulações?",
            "Existem débitos de imposto imobiliário ou de serviços vinculados ao imóvel?",
            "É possível fazer uma inspeção técnica independente antes de assinar?",
        ],
        "checks": [
            ("Titularidade e ônus",
             "Peça a certidão da finca para descartar hipotecas, penhoras ou litígios pendentes sobre o imóvel."),
            ("Construção declarada",
             "Compare os metros construídos reais com os declarados: regularizar uma ampliação não declarada costuma ficar a cargo do comprador."),
            ("Estado da construção",
             "Verifique telhado, umidade, instalação elétrica e hidráulica; uma inspeção técnica custa muito menos que o reparo."),
            ("Débitos do imóvel",
             "Solicite as certidões de imposto imobiliário e de serviços em dia antes de assinar qualquer documento."),
            ("Bairro e acessos",
             "Visite em horários diferentes e confira o estado das ruas, a drenagem e os serviços efetivamente disponíveis."),
        ],
        "costs_lead": "Além do preço, estes são os itens que costumam aparecer na compra de uma casa. Peça o detalhamento por escrito.",
        "costs": [
            ("Escritura e registro", "Honorários de tabelionato e registro da transferência."),
            ("Inspeção técnica", "Avaliação independente de estrutura, umidade e instalações."),
            ("Regularizações", "Declaração de ampliações ou benfeitorias não registradas, se houver."),
            ("Reparos iniciais", "Serviços identificados na inspeção antes de ocupar o imóvel."),
            ("Imposto imobiliário", "Tributo municipal anual; verifique se não há débito acumulado."),
        ],
    },
    "departamentos": {
        "questions": [
            "Qual o valor atual do condomínio e quais serviços estão incluídos?",
            "Posso consultar a convenção de condomínio e as últimas atas de assembleia?",
            "Há obras aprovadas que gerem taxa extra nos próximos meses?",
            "O que exatamente integra a unidade: vaga, depósito e qual fração das áreas comuns?",
        ],
        "checks": [
            ("Propriedade horizontal",
             "Confirme que a unidade está registrada em regime de propriedade horizontal e possui matrícula própria."),
            ("Convenção e condomínio",
             "Peça a convenção de condomínio, o valor da taxa e o detalhe do que ela cobre e do que não cobre."),
            ("Débitos da unidade",
             "Solicite certidão de condomínio em dia: a dívida da unidade normalmente acompanha o imóvel, não o vendedor."),
            ("Obras e fundo de reserva",
             "Pergunte por obras aprovadas em assembleia, pelo fundo de reserva e por taxas extraordinárias previstas."),
            ("Área e acessórios",
             "Confirme a área privativa e a comum, e se vaga ou depósito são unidades independentes com matrícula separada."),
        ],
        "costs_lead": "Comprar em um edifício soma despesas recorrentes ao preço da unidade. Vale estimá-las antes de decidir.",
        "costs": [
            ("Taxa de condomínio", "Despesa recorrente de administração, pessoal e manutenção."),
            ("Escritura e registro", "Honorários de tabelionato e registro da transferência."),
            ("Fundo de reserva", "Aporte para reparos maiores do edifício."),
            ("Taxas extraordinárias", "Obras aprovadas em assembleia, cobradas à parte do condomínio."),
            ("Imposto imobiliário", "Tributo municipal anual correspondente à unidade."),
        ],
    },
    "comerciais": {
        "questions": [
            "O uso do solo e o alvará municipal admitem a atividade que pretendo desenvolver?",
            "Qual carga elétrica disponível, área útil e acesso de carga o ponto oferece?",
            "Como é o fluxo de pedestres e de veículos no corredor e em que horários se concentra?",
            "Há restrições de comunicação visual, horário de carga ou estacionamento na região?",
        ],
        "checks": [
            ("Uso do solo e alvará",
             "Confirme na prefeitura que a atividade prevista é permitida na zona e quais requisitos o alvará exige."),
            ("Aptidão do ponto",
             "Verifique carga elétrica disponível, sanitários, saídas de emergência e área útil real frente à anunciada."),
            ("Acesso e logística",
             "Confira o acesso para carga e descarga, o estacionamento e as restrições de circulação do corredor."),
            ("Titularidade e ônus",
             "Peça a certidão registral da finca e descarte hipotecas, penhoras ou litígios pendentes."),
            ("Entorno comercial",
             "Avalie as atividades vizinhas, o fluxo do corredor e as obras previstas que possam alterar a circulação."),
        ],
        "costs_lead": "Um imóvel comercial se avalia pelo que permite operar. Estes itens costumam integrar o investimento inicial.",
        "costs": [
            ("Escritura e registro", "Honorários de tabelionato e registro da transferência."),
            ("Adequação e alvará", "Obras e trâmites para atender aos requisitos da atividade."),
            ("Instalações e sinalização", "Carga elétrica, climatização e comunicação visual conforme normas locais."),
            ("Serviços com tarifa comercial", "Energia e água costumam ser faturadas em tarifa distinta da residencial."),
            ("Imposto imobiliário", "Tributo municipal anual; verifique se não há débito acumulado."),
        ],
    },
}

# URL slug -> content key, per language
SLUG_KEY = {
    "es": {"terrenos": "terrenos", "casas": "casas",
           "departamentos": "departamentos", "comerciales": "comerciales"},
    "pt-br": {"terrenos": "terrenos", "casas": "casas",
              "apartamentos": "departamentos", "comerciais": "comerciais"},
}

LABELS = {
    "es": {
        "questions_h2": "Preguntas para hacerle a un profesional",
        "costs_h2": "Qué compone el costo de esta compra",
        "checks_h2": "Qué verificar antes de comprar",
        "aspect": "Aspecto",
        "detail": "Qué comprobar",
        "concept": "Concepto",
        "what": "Qué incluye",
        "note": "Los conceptos listados describen el tipo de gasto habitual en esta clase de operación. "
                "InmueblesPY no publica importes: pedí el detalle y el presupuesto a un profesional.",
    },
    "pt-br": {
        "questions_h2": "Perguntas para fazer ao profissional",
        "costs_h2": "O que compõe o custo desta compra",
        "checks_h2": "O que verificar antes de comprar",
        "aspect": "Aspecto",
        "detail": "O que conferir",
        "concept": "Item",
        "what": "O que inclui",
        "note": "Os itens listados descrevem o tipo de despesa habitual nesta classe de operação. "
                "A InmueblesPY não publica valores: peça o detalhamento e o orçamento a um profissional.",
    },
}


def get(lang: str, slug: str):
    key = SLUG_KEY.get(lang, {}).get(slug)
    if not key:
        return None
    return (ES if lang == "es" else PT).get(key)
