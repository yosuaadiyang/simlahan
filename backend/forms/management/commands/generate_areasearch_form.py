from django.core.management.base import BaseCommand

from forms.models.form import Choice, Field, Form, Section


def initialize_area_search_form():
    form = Form.objects.create(
        name="Formulir data dasar pencarian area",
        state="ready",
        title="Formulir data dasar",
        title_ind="Formulir data dasar",
        title_en="Basic information form",
        is_area_form=True,
    )
    main_section = Section.objects.create(
        form=form,
        title="Data pemohon",
        title_ind="Data pemohon",
        title_en="Applicant information",
        identifier="hakijan-tiedot",
        visible=True,
        applicant_type="both",
        add_new_allowed=True,
    )
    applicant_field = Field.objects.create(
        section=main_section,
        label="Pemohon",
        label_ind="Pemohon",
        label_en="Applicant",
        type="radiobuttoninline",
        identifier="hakija",
        enabled=True,
        required=False,
        default_value="1",
    )
    Choice.objects.create(
        field=applicant_field,
        text="Perorangan",
        text_ind="Perorangan",
        text_en="Person",
        value="2",
        has_text_input=False,
    )
    Choice.objects.create(
        field=applicant_field,
        text="Badan usaha/organisasi",
        text_ind="Badan usaha/organisasi",
        text_en="Company/organisation",
        value="1",
        has_text_input=False,
    )

    corporate_section = Section.objects.create(
        form=form,
        parent=main_section,
        title="Data badan usaha",
        title_ind="Data badan usaha",
        title_en="Company information",
        identifier="yrityksen-tiedot",
        visible=True,
        applicant_type="company",
    )
    Field.objects.create(
        section=corporate_section,
        label="Nama badan usaha",
        label_ind="Nama badan usaha",
        label_en="Company name",
        type="textbox",
        identifier="yrityksen-nimi",
        enabled=True,
        required=True,
        sort_order=0,
    )
    Field.objects.create(
        section=corporate_section,
        label="NPWP badan",
        label_ind="NPWP badan",
        label_en="Company tax ID (NPWP)",
        type="textbox",
        identifier="y-tunnus",
        enabled=True,
        required=True,
        sort_order=1,
    )
    Field.objects.create(
        section=corporate_section,
        label="Alamat",
        label_ind="Alamat",
        label_en="Street address",
        type="textbox",
        identifier="katuosoite",
        enabled=True,
        required=True,
        sort_order=2,
    )
    Field.objects.create(
        section=corporate_section,
        label="Kode pos",
        label_ind="Kode pos",
        label_en="Postal code",
        type="textbox",
        identifier="postinumero",
        enabled=True,
        required=True,
        sort_order=3,
    )
    Field.objects.create(
        section=corporate_section,
        label="Kota/Kabupaten",
        label_ind="Kota/Kabupaten",
        label_en="City or regency",
        type="textbox",
        identifier="postitoimipaikka",
        enabled=True,
        required=True,
        sort_order=4,
    )
    Field.objects.create(
        section=corporate_section,
        label="Negara",
        label_ind="Negara",
        label_en="Country",
        type="textbox",
        identifier="maa",
        enabled=True,
        required=False,
        sort_order=5,
        default_value="Indonesia",
    )
    Field.objects.create(
        section=corporate_section,
        label="Nomor telepon",
        label_ind="Nomor telepon",
        label_en="Phone number",
        type="textbox",
        identifier="puhelinnumero",
        enabled=True,
        required=False,
        sort_order=6,
    )
    Field.objects.create(
        section=corporate_section,
        label="Email",
        label_ind="Email",
        label_en="Email",
        type="textbox",
        identifier="sahkoposti",
        enabled=True,
        required=False,
        sort_order=7,
    )

    corporate_contact_section = Section.objects.create(
        form=form,
        parent=corporate_section,
        title="Narahubung",
        title_ind="Narahubung",
        title_en="Contact person",
        identifier="yhteyshenkilo-company",
        applicant_type="company",
    )
    Field.objects.create(
        section=corporate_contact_section,
        label="Nama depan",
        label_ind="Nama depan",
        label_en="First name",
        type="textbox",
        identifier="etunimi",
        enabled=True,
        required=True,
        sort_order=0,
    )
    Field.objects.create(
        section=corporate_contact_section,
        label="Nama belakang",
        label_ind="Nama belakang",
        label_en="Last name",
        type="textbox",
        identifier="Sukunimi",
        enabled=True,
        required=True,
        sort_order=1,
    )
    Field.objects.create(
        section=corporate_contact_section,
        label="Email",
        label_ind="Email",
        label_en="Email",
        type="textbox",
        identifier="sahkoposti",
        enabled=True,
        required=True,
        sort_order=2,
    )
    Field.objects.create(
        section=corporate_contact_section,
        label="Nomor telepon",
        label_ind="Nomor telepon",
        label_en="Phone number",
        type="textbox",
        identifier="puhelinnumero",
        enabled=True,
        required=True,
        sort_order=3,
    )

    invoice_section = Section.objects.create(
        form=form,
        parent=corporate_contact_section,
        title="Data penagihan",
        title_ind="Data penagihan",
        title_en="Billing information",
        identifier="laskutustiedot",
        visible=True,
        applicant_type="company",
    )
    Field.objects.create(
        section=invoice_section,
        label="Alamat e-faktur",
        label_ind="Alamat e-faktur",
        label_en="E-invoice address",
        type="textbox",
        identifier="verkkolaskuosoite",
        enabled=True,
        required=False,
        sort_order=0,
    )
    Field.objects.create(
        section=invoice_section,
        label="ID perantara",
        label_ind="ID perantara",
        label_en="Intermediary ID",
        type="textbox",
        identifier="valittajan-tunnus",
        enabled=True,
        required=False,
        sort_order=1,
    )
    Field.objects.create(
        section=invoice_section,
        label="Referensi tagihan (akan tercantum pada tagihan)",
        label_ind="Referensi tagihan (akan tercantum pada tagihan)",
        label_en="Billing reference (will appear on the invoice)",
        type="textbox",
        identifier="laskutusviite",
        enabled=True,
        required=False,
        sort_order=2,
    )

    invoice_other_section = Section.objects.create(
        form=form,
        parent=invoice_section,
        title="Data penagihan lain",
        title_ind="Data penagihan lain",
        title_en="Other billing information",
        identifier="muut-laskutustiedot",
        visible=True,
        applicant_type="company",
    )
    Field.objects.create(
        section=invoice_other_section,
        label="Alamat penagihan lain",
        label_ind="Alamat penagihan lain",
        label_en="Other billing address",
        type="checkbox",
        identifier="laskutusosoite-muu",
        enabled=True,
        required=False,
        sort_order=0,
        hint_text="Isi hanya jika terdapat alamat penagihan lain.",
        hint_text_ind="Isi hanya jika terdapat alamat penagihan lain.",
        hint_text_en="Fill in only if there is another billing address.",
    )
    invoice_section_language = Field.objects.create(
        section=invoice_other_section,
        label="Bahasa",
        label_ind="Bahasa",
        label_en="Language",
        type="dropdown",
        identifier="kieli",
        enabled=True,
        required=False,
        sort_order=1,
    )
    Choice.objects.create(
        field=invoice_section_language,
        text="Bahasa Indonesia",
        text_ind="Bahasa Indonesia",
        text_en="Indonesian",
        value="indonesia",
        has_text_input=False,
    )
    Choice.objects.create(
        field=invoice_section_language,
        text="Bahasa daerah/lainnya",
        text_ind="Bahasa daerah/lainnya",
        text_en="Other language",
        value="lainnya",
        has_text_input=False,
    )
    Choice.objects.create(
        field=invoice_section_language,
        text="Bahasa Inggris",
        text_ind="Bahasa Inggris",
        text_en="English",
        value="inggris",
        has_text_input=False,
    )

    Field.objects.create(
        section=invoice_other_section,
        label="u.p.",
        label_ind="u.p.",
        label_en="c/o",
        type="textbox",
        identifier="c_o",
        enabled=True,
        required=False,
        sort_order=2,
    )
    Field.objects.create(
        section=invoice_other_section,
        label="Alamat",
        label_ind="Alamat",
        label_en="Street address",
        type="textbox",
        identifier="katuosoite",
        enabled=True,
        required=False,
        sort_order=3,
    )
    Field.objects.create(
        section=invoice_other_section,
        label="Kode pos",
        label_ind="Kode pos",
        label_en="Postal number",
        type="textbox",
        identifier="postinumero",
        enabled=True,
        required=False,
        sort_order=4,
    )
    Field.objects.create(
        section=invoice_other_section,
        label="Kota/Kabupaten",
        label_ind="Kota/Kabupaten",
        label_en="City or regency",
        type="textbox",
        identifier="postitoimipaikka",
        enabled=True,
        required=False,
        sort_order=5,
    )
    Field.objects.create(
        section=invoice_other_section,
        label="Negara",
        label_ind="Negara",
        label_en="Country",
        type="textbox",
        identifier="maa",
        enabled=True,
        required=False,
        sort_order=6,
        default_value="Indonesia",
    )
    Field.objects.create(
        section=invoice_other_section,
        label="Nama",
        label_ind="Nama",
        label_en="Name",
        type="textbox",
        identifier="nimi",
        enabled=True,
        required=False,
        sort_order=7,
    )
    Field.objects.create(
        section=invoice_other_section,
        label="Nomor telepon",
        label_ind="Nomor telepon",
        label_en="Phone number",
        type="textbox",
        identifier="puhelinnumero",
        enabled=True,
        required=False,
        sort_order=8,
    )
    Field.objects.create(
        section=invoice_other_section,
        label="Email",
        label_ind="Email",
        label_en="Email",
        type="textbox",
        identifier="sahkoposti",
        enabled=True,
        required=False,
        sort_order=9,
    )
    Field.objects.create(
        section=invoice_other_section,
        label="Referensi tagihan (akan tercantum pada tagihan)",
        label_ind="Referensi tagihan (akan tercantum pada tagihan)",
        label_en="Billing reference (will appear on the invoice)",
        type="textbox",
        identifier="laskutusviite",
        enabled=True,
        required=False,
        sort_order=10,
    )

    people_section = Section.objects.create(
        form=form,
        parent=main_section,
        title="Data perorangan",
        title_ind="Data perorangan",
        title_en="Personal information",
        identifier="henkilon-tiedot",
        visible=True,
        applicant_type="person",
    )
    Field.objects.create(
        section=people_section,
        label="Nama depan",
        label_ind="Nama depan",
        label_en="First name",
        type="textbox",
        identifier="etunimi",
        enabled=True,
        required=True,
        sort_order=0,
    )
    Field.objects.create(
        section=people_section,
        label="Nama belakang",
        label_ind="Nama belakang",
        label_en="Last name",
        type="textbox",
        identifier="Sukunimi",
        enabled=True,
        required=True,
        sort_order=1,
    )
    Field.objects.create(
        section=people_section,
        label="NIK",
        label_ind="NIK",
        label_en="National identity number (NIK)",
        type="textbox",
        identifier="henkilotunnus",
        enabled=True,
        required=True,
        sort_order=2,
    )
    people_section_language = Field.objects.create(
        section=people_section,
        label="Bahasa",
        label_ind="Bahasa",
        label_en="Language",
        type="dropdown",
        identifier="kieli",
        enabled=True,
        required=True,
        sort_order=3,
    )

    Choice.objects.create(
        field=people_section_language,
        text="Bahasa Indonesia",
        text_ind="Bahasa Indonesia",
        text_en="Indonesian",
        value="indonesia",
        has_text_input=False,
    )
    Choice.objects.create(
        field=people_section_language,
        text="Bahasa daerah/lainnya",
        text_ind="Bahasa daerah/lainnya",
        text_en="Other language",
        value="lainnya",
        has_text_input=False,
    )
    Choice.objects.create(
        field=people_section_language,
        text="Bahasa Inggris",
        text_ind="Bahasa Inggris",
        text_en="English",
        value="inggris",
        has_text_input=False,
    )

    Field.objects.create(
        section=people_section,
        label="Nomor telepon",
        label_ind="Nomor telepon",
        label_en="Phone number",
        type="textbox",
        identifier="puhelinnumero",
        enabled=True,
        required=True,
        sort_order=4,
    )
    Field.objects.create(
        section=people_section,
        label="Email",
        label_ind="Email",
        label_en="Email",
        type="textbox",
        identifier="sahkoposti",
        enabled=True,
        required=True,
        sort_order=5,
    )
    Field.objects.create(
        section=people_section,
        label="Alamat",
        label_ind="Alamat",
        label_en="Street address",
        type="textbox",
        identifier="katuosoite",
        enabled=True,
        required=True,
        sort_order=6,
    )
    Field.objects.create(
        section=people_section,
        label="Kode pos",
        label_ind="Kode pos",
        label_en="Postal number",
        type="textbox",
        identifier="postinumero",
        enabled=True,
        required=True,
        sort_order=7,
    )
    Field.objects.create(
        section=people_section,
        label="Kota/Kabupaten",
        label_ind="Kota/Kabupaten",
        label_en="City or regency",
        type="textbox",
        identifier="postitoimipaikka",
        enabled=True,
        required=True,
        sort_order=8,
    )
    Field.objects.create(
        section=people_section,
        label="Negara",
        label_ind="Negara",
        label_en="Country",
        type="textbox",
        identifier="maa",
        enabled=True,
        required=True,
        sort_order=9,
        default_value="Indonesia",
    )
    non_disclosure = Field.objects.create(
        section=people_section,
        label="Data dirahasiakan karena alasan keamanan",
        label_ind="Data dirahasiakan karena alasan keamanan",
        label_en="Non-disclosure for safety reasons",
        type="dropdown",
        identifier="turvakielto",
        enabled=True,
        required=False,
        sort_order=10,
        default_value="ei",
    )
    Choice.objects.create(
        field=non_disclosure,
        text="Tidak",
        text_ind="Tidak",
        text_en="No",
        value="ei",
        has_text_input=False,
    )
    Choice.objects.create(
        field=non_disclosure,
        text="Ya",
        text_ind="Ya",
        text_en="Yes",
        value="kyllä",
        has_text_input=False,
    )

    contact_section = Section.objects.create(
        form=form,
        parent=people_section,
        title="Narahubung",
        title_ind="Narahubung",
        title_en="Contact person",
        identifier="yhteyshenkilo-1",
        applicant_type="person",
    )
    Field.objects.create(
        section=contact_section,
        label="Berbeda dengan pemohon",
        label_ind="Berbeda dengan pemohon",
        label_en="Different from the applicant",
        type="checkbox",
        identifier="eri-kuin-hakija",
        enabled=True,
        required=False,
        sort_order=0,
        hint_text="Isi hanya jika narahubung berbeda dengan pemohon.",
        hint_text_ind="Isi hanya jika narahubung berbeda dengan pemohon.",
        hint_text_en="Fill in only if the contact person is different from the applicant.",
    )
    Field.objects.create(
        section=contact_section,
        label="Nama depan",
        label_ind="Nama depan",
        label_en="First name",
        type="textbox",
        identifier="etunimi",
        enabled=True,
        required=False,
        sort_order=1,
    )
    Field.objects.create(
        section=contact_section,
        label="Nama belakang",
        label_ind="Nama belakang",
        label_en="Last name",
        type="textbox",
        identifier="Sukunimi",
        enabled=True,
        required=False,
        sort_order=2,
    )
    Field.objects.create(
        section=contact_section,
        label="Email",
        label_ind="Email",
        label_en="Email",
        type="textbox",
        identifier="sahkoposti",
        enabled=True,
        required=False,
        sort_order=3,
    )
    Field.objects.create(
        section=contact_section,
        label="Nomor telepon",
        label_ind="Nomor telepon",
        label_en="Phone number",
        type="textbox",
        identifier="puhelinnumero",
        enabled=True,
        required=False,
        sort_order=4,
    )

    invoice_section2 = Section.objects.create(
        form=form,
        parent=people_section,
        title="Penerima tagihan",
        title_ind="Penerima tagihan",
        title_en="Invoice recipient",
        identifier="laskunsaaja",
        applicant_type="person",
    )
    Field.objects.create(
        section=invoice_section2,
        label="Berbeda dengan pemohon",
        label_ind="Berbeda dengan pemohon",
        label_en="Different from the applicant",
        type="checkbox",
        identifier="eri-kuin-hakija",
        enabled=True,
        required=False,
        sort_order=0,
        hint_text="Isi hanya jika terdapat alamat penagihan lain.",
        hint_text_ind="Isi hanya jika terdapat alamat penagihan lain.",
        hint_text_en="Fill in only if there is another billing address.",
    )
    invoice_section2_language = Field.objects.create(
        section=invoice_section2,
        label="Bahasa",
        label_ind="Bahasa",
        label_en="Language",
        type="dropdown",
        identifier="kieli",
        enabled=True,
        required=False,
        sort_order=1,
    )

    Choice.objects.create(
        field=invoice_section2_language,
        text="Bahasa Indonesia",
        text_ind="Bahasa Indonesia",
        text_en="Indonesian",
        value="indonesia",
        has_text_input=False,
    )
    Choice.objects.create(
        field=invoice_section2_language,
        text="Bahasa daerah/lainnya",
        text_ind="Bahasa daerah/lainnya",
        text_en="Other language",
        value="lainnya",
        has_text_input=False,
    )
    Choice.objects.create(
        field=invoice_section2_language,
        text="Bahasa Inggris",
        text_ind="Bahasa Inggris",
        text_en="English",
        value="inggris",
        has_text_input=False,
    )
    Field.objects.create(
        section=invoice_section2,
        label="u.p.",
        label_ind="u.p.",
        label_en="c/o",
        type="textbox",
        identifier="c_o",
        enabled=True,
        required=False,
        sort_order=2,
    )
    Field.objects.create(
        section=invoice_section2,
        label="Alamat",
        label_ind="Alamat",
        label_en="Street address",
        type="textbox",
        identifier="katuosoite",
        enabled=True,
        required=False,
        sort_order=3,
    )
    Field.objects.create(
        section=invoice_section2,
        label="Kode pos",
        label_ind="Kode pos",
        label_en="Postal number",
        type="textbox",
        identifier="postinumero",
        enabled=True,
        required=False,
        sort_order=4,
    )
    Field.objects.create(
        section=invoice_section2,
        label="Kota/Kabupaten",
        label_ind="Kota/Kabupaten",
        label_en="City or regency",
        type="textbox",
        identifier="postitoimipaikka",
        enabled=True,
        required=False,
        sort_order=5,
    )
    Field.objects.create(
        section=invoice_section2,
        label="Negara",
        label_ind="Negara",
        label_en="Country",
        type="textbox",
        identifier="maa",
        enabled=True,
        required=False,
        sort_order=6,
        default_value="Indonesia",
    )
    Field.objects.create(
        section=invoice_section2,
        label="Referensi tagihan (akan tercantum pada tagihan)",
        label_ind="Referensi tagihan (akan tercantum pada tagihan)",
        label_en="Billing reference (will appear on the invoice)",
        type="textbox",
        identifier="laskutusviite",
        enabled=True,
        required=False,
        sort_order=7,
    )
    Field.objects.create(
        section=invoice_section2,
        label="Nama",
        label_ind="Nama",
        label_en="Name",
        type="textbox",
        identifier="nimi",
        enabled=True,
        required=False,
        sort_order=8,
    )
    Field.objects.create(
        section=invoice_section2,
        label="Email",
        label_ind="Email",
        label_en="Email",
        type="textbox",
        identifier="sahkoposti",
        enabled=True,
        required=False,
        sort_order=9,
    )
    Field.objects.create(
        section=invoice_section2,
        label="Nomor telepon",
        label_ind="Nomor telepon",
        label_en="Phone number",
        type="textbox",
        identifier="puhelinnumero",
        enabled=True,
        required=False,
        sort_order=10,
    )

    decision_section = Section.objects.create(
        form=form,
        title="Saya setuju",
        title_ind="Saya setuju",
        title_en="I agree",
        identifier="päätöksen-toimitus",
    )
    Field.objects.create(
        section=decision_section,
        label="Saya menyatakan bahwa data yang saya berikan adalah benar.",
        label_ind="Saya menyatakan bahwa data yang saya berikan adalah benar.",
        label_en="I certify that the information I have provided is correct",
        type="checkbox",
        identifier="vakuutan-antamani-tiedot-oikeiksi",
        enabled=True,
        required=True,
        sort_order=0,
    )
    Field.objects.create(
        section=decision_section,
        label="Saya menyatakan bahwa pemohon tidak termasuk dalam daftar sanksi.",
        label_ind="Saya menyatakan bahwa pemohon tidak termasuk dalam daftar sanksi.",
        label_en="I certify that the applicants are not subject to sanctions.",
        hint_text=(
            "Dengan menjawab YA, pemohon menyatakan bahwa pemohon maupun pemilik "
            "langsung/tidak langsung, penanggung jawab, atau pihak terkaitnya tidak"
            " termasuk dalam daftar sanksi dan tidak dikenai pemblokiran dana, "
            "termasuk anggota direksi, komisaris, atau pihak yang memiliki "
            "kewenangan mewakili, memutus, atau mengawasi."
        ),
        hint_text_ind=(
            "Dengan menjawab YA, pemohon menyatakan bahwa pemohon maupun pemilik "
            "langsung/tidak langsung, penanggung jawab, atau pihak terkaitnya tidak"
            " termasuk dalam daftar sanksi dan tidak dikenai pemblokiran dana, "
            "termasuk anggota direksi, komisaris, atau pihak yang memiliki "
            "kewenangan mewakili, memutus, atau mengawasi."
        ),
        hint_text_en="""By answering YES, the applicant certifies that they or
        any of their direct or indirect owners, officers, directors or other
        persons associated with them are not subject to sanctions or that
        sanctions or asset freezing orders have not been imposed on the
        applicant, members of their administrative, management or supervisory
        bodies, or persons or entities with powers of representation, decision
        making, control or supervision.""",
        type="checkbox",
        identifier="pakotelista-vakuutus",
        enabled=True,
        required=True,
        sort_order=1,
    )
    Field.objects.create(
        section=decision_section,
        label=(
            "Pemohon setuju bahwa keputusan atau dokumen lain dapat disampaikan "
            "secara elektronik ke alamat email yang saya cantumkan."
        ),
        label_ind=(
            "Pemohon setuju bahwa keputusan atau dokumen lain dapat disampaikan "
            "secara elektronik ke alamat email yang saya cantumkan."
        ),
        label_en=(
            "The applicant agrees that a decision or other document may be served "
            "electronically to the email address I have provided."
        ),
        hint_text=(
            "Keputusan atau dokumen lain dikirim ke email narahubung pemohon. Jika "
            "pemohon perorangan dan narahubung tidak dicantumkan, keputusan atau "
            "dokumen lain dikirim ke email pemohon."
        ),
        hint_text_ind=(
            "Keputusan atau dokumen lain dikirim ke email narahubung pemohon. Jika "
            "pemohon perorangan dan narahubung tidak dicantumkan, keputusan atau "
            "dokumen lain dikirim ke email pemohon."
        ),
        hint_text_en="""The decision or other document will be sent to the email
        address of the applicant's contact person. If the applicant is a private
        person and no contact person is indicated, the decision or other
        document will be sent to the applicant's e-mail address.""",
        type="checkbox",
        identifier="sahkoisesti-ilmoittamaani-sahkopostiosoitteeseen",
        enabled=True,
        required=False,
        sort_order=2,
    )
    Field.objects.create(
        section=decision_section,
        label=(
            "Saya menyetujui penyimpanan dan pemrosesan data saya sesuai "
            "pemberitahuan pelindungan data pribadi instansi pengelola lahan."
        ),
        label_ind=(
            "Saya menyetujui penyimpanan dan pemrosesan data saya sesuai "
            "pemberitahuan pelindungan data pribadi instansi pengelola lahan."
        ),
        label_en=(
            "I consent to the storage and processing of my data in accordance with "
            "the land management agency's personal data protection notice."
        ),
        hint_text=(
            "Saya telah membaca pemberitahuan pelindungan data pribadi terkait "
            "pemrosesan data pribadi (UU 27/2022)."
        ),
        hint_text_ind=(
            "Saya telah membaca pemberitahuan pelindungan data pribadi terkait "
            "pemrosesan data pribadi (UU 27/2022)."
        ),
        hint_text_en=(
            "I have read the personal data protection notices concerning the "
            "processing of personal data (Law 27/2022)."
        ),
        type="checkbox",
        identifier="hyvaksyn-tietojeni-tallentamisen",
        enabled=True,
        required=False,
        sort_order=3,
    )

    return form


class Command(BaseCommand):
    help = "Generates an Area Search form."

    def handle(self, *args, **options):
        initialize_area_search_form()
